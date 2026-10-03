import {
  ANALYSIS_PRICE_IDR,
  applyNotification,
  attachCharge,
  createOrder,
  expireOrder,
  failOrder,
  isPaidStatus,
  OrderNotFoundError,
  type MidtransNotification,
  type Order,
} from "./domain";
import {
  createQrisCharge,
  fetchTransactionStatus,
  type MidtransConfig,
} from "./midtrans";
import type { OrderStore } from "./order-store";

export interface BillingGateway {
  chargeQris(input: {
    orderId: string;
    grossAmount: number;
    email: string | null;
  }): Promise<{ transactionId: string; qrUrl: string }>;
  transactionStatus(orderId: string): Promise<{
    transactionStatus: string;
    fraudStatus?: string;
  }>;
}

export class MidtransBillingGateway implements BillingGateway {
  constructor(private readonly config: MidtransConfig) {}

  chargeQris(input: {
    orderId: string;
    grossAmount: number;
    email: string | null;
  }): Promise<{ transactionId: string; qrUrl: string }> {
    return createQrisCharge(this.config, input);
  }

  transactionStatus(orderId: string): Promise<{
    transactionStatus: string;
    fraudStatus?: string;
  }> {
    return fetchTransactionStatus(this.config, orderId);
  }
}

export interface BillingServiceDependencies {
  store: OrderStore;
  gateway: BillingGateway;
  now: () => Date;
  generateOrderId: () => string;
}

export class BillingService {
  constructor(private readonly deps: BillingServiceDependencies) {}

  /**
   * Start a checkout.
   *
   * Replaying the same idempotency key returns the existing order instead of
   * charging again, so a double-tapped pay button or a client retry cannot
   * create a second QR for one intent.
   */
  async startCheckout(input: {
    userId: string;
    email: string | null;
    idempotencyKey: string;
    consentedToUnvalidatedCountry: boolean;
  }): Promise<Order> {
    const existing = await this.deps.store.findByIdempotencyKey(input.userId, input.idempotencyKey);
    if (existing) return existing;

    const now = this.deps.now().toISOString();
    const order = createOrder({
      id: this.deps.generateOrderId(),
      userId: input.userId,
      email: input.email,
      now,
      idempotencyKey: input.idempotencyKey,
      consentedToUnvalidatedCountry: input.consentedToUnvalidatedCountry,
    });
    await this.deps.store.create(order);

    try {
      const charge = await this.deps.gateway.chargeQris({
        orderId: order.id,
        grossAmount: ANALYSIS_PRICE_IDR,
        email: order.email,
      });
      return await this.deps.store.update(
        attachCharge(order, { transactionId: charge.transactionId, qrUrl: charge.qrUrl }, now),
      );
    } catch (error) {
      // The charge never completed, so no money moved. Mark the order failed so
      // the stale pending row cannot be mistaken for a payable QR later.
      await this.deps.store.update(failOrder(order, this.deps.now().toISOString()));
      throw error;
    }
  }

  /** Record a signed provider notification. Safe to call more than once. */
  async handleNotification(
    notification: Pick<MidtransNotification, "orderId" | "transactionStatus" | "fraudStatus">,
  ): Promise<Order> {
    const order = await this.deps.store.get(notification.orderId);
    if (!order) throw new OrderNotFoundError();

    return this.deps.store.update(
      applyNotification(order, notification, this.deps.now().toISOString()),
    );
  }

  /**
   * Read an order for its owner, reconciling with the provider first.
   *
   * The provider is the source of truth for money: a webhook may be late or
   * lost, and telling someone their QR is unpaid when it settled would hide a
   * paid purchase from them.
   */
  async getOrderForUser(orderId: string, userId: string): Promise<Order> {
    const order = await this.deps.store.get(orderId);
    if (!order || order.userId !== userId) throw new OrderNotFoundError();
    if (order.status === "pending" || isPaidStatus(order.status)) {
      return this.reconcile(order);
    }
    return order;
  }

  /** The credit this user may spend, if any. */
  async getAvailableCredit(userId: string): Promise<Order | null> {
    const order = await this.deps.store.findPaidCredit(userId);
    return order ? this.reconcile(order) : null;
  }

  /**
   * Spend a credit for an analysis that produced a result.
   *
   * The transition is a single atomic compare-and-set in the store, so two
   * concurrent requests cannot both spend one credit. The caller only invokes
   * this once the model has returned a usable score, which is what keeps a
   * backend failure from costing the user anything.
   */
  async consumeCredit(userId: string, orderId: string | null): Promise<Order> {
    if (!orderId) throw new OrderNotFoundError();
    // consumeIfPaid returns null unless the order was still paid, and performs
    // the state change itself; re-applying consumeOrder here would reject the
    // very row we just transitioned.
    const consumed = await this.deps.store.consumeIfPaid(
      orderId,
      this.deps.now().toISOString(),
    );
    if (!consumed || consumed.userId !== userId) throw new OrderNotFoundError();
    return consumed;
  }

  /** Refresh a pending order's state from the provider. */
  private async reconcile(order: Order): Promise<Order> {
    const now = this.deps.now().toISOString();
    if (order.status !== "pending") return order;
    if (Date.parse(now) >= Date.parse(order.expiresAt)) {
      return this.deps.store.update(expireOrder(order, now));
    }

    let status: { transactionStatus: string; fraudStatus?: string };
    try {
      status = await this.deps.gateway.transactionStatus(order.id);
    } catch {
      // A provider outage must not consume or invent state; keep what we know.
      return order;
    }
    return this.deps.store.update(applyNotification(order, status, now));
  }
}