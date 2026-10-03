import { FirestoreOrderStore } from "./firestore-order-store";
import { readMidtransConfig } from "./midtrans";
import { generateOrderId } from "./http";
import { InMemoryOrderStore, type OrderStore } from "./order-store";
import { BillingService, MidtransBillingGateway } from "./service";

/**
 * One billing service per process.
 *
 * Cached because the Firestore client opens its own connection pool; rebuilding
 * it per request would multiply connections on a busy instance.
 */
let cached: { service: BillingService; store: OrderStore } | null = null;

/**
 * Build the billing service for this environment.
 *
 * Returns null when no payment credentials exist: the app then serves free
 * screening instead of pretending checkout is available. The in-memory store is
 * only ever chosen for local development — on serverless it would lose orders
 * between instances, so production uses Firestore and is expected to have the
 * Firebase Admin credentials.
 */
export function resolveBillingService(): {
  service: BillingService;
  store: OrderStore;
} | null {
  if (cached) return cached;

  const config = readMidtransConfig();
  if (!config) return null;

  const store: OrderStore =
    process.env.NODE_ENV === "production" ? new FirestoreOrderStore() : new InMemoryOrderStore();

  cached = {
    store,
    service: new BillingService({
      store,
      gateway: new MidtransBillingGateway(config),
      now: () => new Date(),
      generateOrderId,
    }),
  };
  return cached;
}

/** Test seam: force the next resolve to build a service from scratch. */
export function resetBillingServiceForTests(): void {
  cached = null;
}