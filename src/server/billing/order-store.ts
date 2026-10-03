import type { Order } from "./domain";

/**
 * Order persistence port.
 *
 * Two adapters exist because a credit is money: Firestore in production (so a
 * webhook and an analysis request can hit different instances and still see the
 * same order), and an in-memory map for tests. Nothing above this interface
 * knows which one it has.
 */
export interface OrderStore {
  create(order: Order): Promise<Order>;
  get(orderId: string): Promise<Order | null>;
  findByIdempotencyKey(userId: string, idempotencyKey: string): Promise<Order | null>;
  findPaidCredit(userId: string): Promise<Order | null>;
  update(order: Order): Promise<Order>;
  /**
   * Mark a paid order consumed only if it is still paid, so two concurrent
   * analyses cannot both spend one credit.
   */
  consumeIfPaid(orderId: string, now: string): Promise<Order | null>;
}

export class InMemoryOrderStore implements OrderStore {
  private readonly orders = new Map<string, Order>();

  async create(order: Order): Promise<Order> {
    const existing = this.orders.get(order.id);
    if (existing) return existing;
    this.orders.set(order.id, order);
    return order;
  }

  async get(orderId: string): Promise<Order | null> {
    return this.orders.get(orderId) ?? null;
  }

  async findByIdempotencyKey(userId: string, idempotencyKey: string): Promise<Order | null> {
    return (
      [...this.orders.values()].find(
        (order) => order.userId === userId && order.idempotencyKey === idempotencyKey,
      ) ?? null
    );
  }

  async findPaidCredit(userId: string): Promise<Order | null> {
    return (
      [...this.orders.values()]
        .filter((order) => order.userId === userId && order.status === "paid")
        .sort((left, right) => Date.parse(right.paidAt ?? "") - Date.parse(left.paidAt ?? ""))[0] ??
      null
    );
  }

  async update(order: Order): Promise<Order> {
    this.orders.set(order.id, order);
    return order;
  }

  async consumeIfPaid(orderId: string, now: string): Promise<Order | null> {
    const order = this.orders.get(orderId);
    if (!order || order.status !== "paid") return null;
    const consumed: Order = { ...order, status: "consumed", consumedAt: now, updatedAt: now };
    this.orders.set(orderId, consumed);
    return consumed;
  }
}