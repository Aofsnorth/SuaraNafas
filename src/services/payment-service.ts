import { getFirebaseAuth } from "@/lib/firebase";

export interface BillingConfig {
  enabled: boolean;
  priceIdr: number;
  currency: string;
  sandbox?: boolean;
  unvalidatedCountries?: string[];
}

export type OrderStatus = "pending" | "paid" | "consumed" | "expired" | "failed";

export interface CheckoutSession {
  orderId: string;
  status: OrderStatus;
  amountIdr: number;
  currency: string;
  qrUrl: string | null;
  expiresAt: string;
}

const STATUS_POLL_INTERVAL_MS = 4_000;
const STATUS_POLL_TIMEOUT_MS = 20 * 60 * 1000;

async function authToken(): Promise<string | null> {
  const auth = getFirebaseAuth();
  if (!auth) return null;
  // Force a refresh: a stale token is the most common cause of a spurious 401
  // on a long-lived checkout flow.
  return auth.currentUser?.getIdToken(true) ?? null;
}

async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await authToken();
  if (!token) throw new Error("AUTH_REQUIRED");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(path, { ...init, headers });
}

async function readError(response: Response): Promise<string> {
  const body = (await response.json().catch(() => ({}))) as {
    error?: string;
    code?: string;
  };
  return body.error ?? `Permintaan gagal (${response.status}).`;
}

export async function fetchBillingConfig(): Promise<BillingConfig | null> {
  try {
    const response = await fetch("/api/billing/checkout", { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as BillingConfig;
  } catch {
    // Billing being unreachable must not break free screening; the caller
    // treats "unknown config" as "offer the analysis without a paywall".
    return null;
  }
}

export async function startCheckout(input: {
  acceptsUnvalidatedCountry: boolean;
  idempotencyKey: string;
}): Promise<CheckoutSession> {
  const response = await authorizedFetch("/api/billing/checkout", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": input.idempotencyKey,
    },
    body: JSON.stringify({ acceptsUnvalidatedCountry: input.acceptsUnvalidatedCountry }),
  });

  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as CheckoutSession;
}

export async function fetchOrderStatus(orderId: string): Promise<CheckoutSession> {
  const response = await authorizedFetch(
    `/api/billing/orders/${encodeURIComponent(orderId)}`,
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error(await readError(response));
  return (await response.json()) as CheckoutSession;
}

/**
 * Poll until the QR is paid, expired, or failed.
 *
 * The server reconciles with the payment provider on each poll, so this works
 * even if the provider's webhook is delayed or lost — the client's poll is a
 * safety net, not the primary mechanism.
 */
export async function waitForPayment(orderId: string): Promise<OrderStatus> {
  const deadline = Date.now() + STATUS_POLL_TIMEOUT_MS;

  while (Date.now() < deadline) {
    const order = await fetchOrderStatus(orderId);
    if (order.status !== "pending") return order.status;
    await new Promise((resolve) => setTimeout(resolve, STATUS_POLL_INTERVAL_MS));
  }

  throw new Error(
    "Status pembayaran tidak dapat dikonfirmasi dalam batas waktu. Periksa apakah pembayaran Anda sudah masuk.",
  );
}

/**
 * A stable key for one checkout attempt.
 *
 * Generated once per attempt so a double tap or a retry after a network error
 * reuses the same order instead of charging twice.
 */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `key-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}