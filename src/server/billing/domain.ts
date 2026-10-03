/**
 * Payment domain rules for the paid screening credit.
 *
 * Kept free of Next.js, Firebase, and Midtrans imports so the rules can be
 * tested directly: an order's legal transitions are the part that decides
 * whether a customer is charged or served.
 */

export const ANALYSIS_PRICE_IDR = 5_000;

/** A QR must be paid within this window; Midtrans expires QRIS itself too. */
export const ORDER_EXPIRY_MS = 30 * 60 * 1000;

export type OrderStatus =
  | "pending"
  | "paid"
  | "consumed"
  | "expired"
  | "failed";

export interface Order {
  id: string;
  userId: string;
  email: string | null;
  amountIdr: number;
  status: OrderStatus;
  provider: "midtrans";
  transactionId: string | null;
  qrUrl: string | null;
  createdAt: string;
  updatedAt: string;
  expiresAt: string;
  paidAt: string | null;
  consumedAt: string | null;
  /** Order id supplied by the client to make checkout retries idempotent. */
  idempotencyKey: string;
  /**
   * Whether the buyer consented, before paying, to a score computed for a
   * country the model was never validated on.
   *
   * Recorded server-side at checkout on purpose: the consent gate must not be
   * a client-supplied flag, or anyone could send it on any request.
   */
  consentedToUnvalidatedCountry: boolean;
}

export interface MidtransChargeRequest {
  orderId: string;
  grossAmount: number;
  email: string | null;
}

export interface MidtransChargeResult {
  transactionId: string;
  qrUrl: string;
}

export interface MidtransNotification {
  orderId: string;
  transactionStatus: string;
  /** Absent for payment methods that skip fraud scoring, so it is optional. */
  fraudStatus?: string;
  grossAmount: string;
  statusCode: string;
  signatureKey: string;
}

export class BillingError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "BillingError";
    this.code = code;
    this.status = status;
  }
}

export class OrderNotFoundError extends BillingError {
  constructor() {
    super("ORDER_NOT_FOUND", "Order tidak ditemukan.", 404);
    this.name = "OrderNotFoundError";
  }
}

/**
 * Which terminal status a provider notification implies.
 *
 * Only `settlement` and `capture` count as paid. `pending` is deliberately not
 * terminal: a later notification will follow, and treating it as paid would
 * deliver a free service for an unpaid QR.
 */
export function paymentStatus(
  notification: Pick<MidtransNotification, "transactionStatus"> &
    Partial<Pick<MidtransNotification, "fraudStatus">>,
): "paid" | "pending" | "failed" {
  const status = notification.transactionStatus.toLowerCase();
  const fraud = notification.fraudStatus?.toLowerCase();

  if (status === "settlement" || status === "capture") {
    return fraud && fraud !== "accept" ? "pending" : "paid";
  }
  if (status === "pending" || status === "authorize") return "pending";
  return "failed";
}

export function isPaidStatus(status: OrderStatus): boolean {
  return status === "paid" || status === "consumed";
}

export function isExpired(order: Order, now: string): boolean {
  return Date.parse(now) >= Date.parse(order.expiresAt);
}

export function expireOrder(order: Order, now: string): Order {
  if (order.status !== "pending") return order;
  return { ...order, status: "expired", updatedAt: now };
}

export function failOrder(order: Order, now: string): Order {
  if (order.status !== "pending") return order;
  return { ...order, status: "failed", updatedAt: now };
}

/**
 * Apply a provider notification to an order.
 *
 * Idempotent by construction: a replayed settlement on an already-paid or
 * already-consumed order returns the order unchanged, which is what Midtrans
 * retries require. A paid order is never downgraded by a late `pending`.
 */
export function applyNotification(
  order: Order,
  notification: Pick<MidtransNotification, "transactionStatus"> &
    Partial<Pick<MidtransNotification, "fraudStatus">>,
  receivedAt: string,
): Order {
  if (isPaidStatus(order.status)) return order;

  const next = paymentStatus(notification);
  if (next === "pending") {
    return isExpired(order, receivedAt) ? expireOrder(order, receivedAt) : order;
  }
  if (next === "failed") {
    return failOrder(order, receivedAt);
  }
  // Funds arrived after our own expiry window. Still record the payment: the
  // customer paid, and the credit is owed to them.
  return { ...order, status: "paid", updatedAt: receivedAt, paidAt: receivedAt };
}

export function createOrder(input: {
  id: string;
  userId: string;
  email: string | null;
  now: string;
  idempotencyKey: string;
  consentedToUnvalidatedCountry: boolean;
}): Order {
  if (input.idempotencyKey.trim().length < 8) {
    throw new BillingError(
      "INVALID_IDEMPOTENCY_KEY",
      "Kunci idempotensi tidak valid.",
      400,
    );
  }
  const createdAtMs = Date.parse(input.now);
  return {
    id: input.id,
    userId: input.userId,
    email: input.email,
    amountIdr: ANALYSIS_PRICE_IDR,
    status: "pending",
    provider: "midtrans",
    transactionId: null,
    qrUrl: null,
    createdAt: input.now,
    updatedAt: input.now,
    expiresAt: new Date(createdAtMs + ORDER_EXPIRY_MS).toISOString(),
    paidAt: null,
    consumedAt: null,
    idempotencyKey: input.idempotencyKey,
    consentedToUnvalidatedCountry: input.consentedToUnvalidatedCountry,
  };
}

export function attachCharge(
  order: Order,
  charge: MidtransChargeResult,
  now: string,
): Order {
  return {
    ...order,
    transactionId: charge.transactionId,
    qrUrl: charge.qrUrl,
    updatedAt: now,
  };
}

/** Spend a paid credit. Only a paid order can be consumed, and only once. */
export function consumeOrder(order: Order, now: string): Order {
  if (order.status !== "paid") {
    throw new BillingError(
      "CREDIT_NOT_AVAILABLE",
      "Kredit analisis tidak tersedia untuk order ini.",
      409,
    );
  }
  return { ...order, status: "consumed", consumedAt: now, updatedAt: now };
}