import {
  getFirestore,
  type DocumentData,
  type Firestore,
} from "firebase-admin/firestore";

import type { Order } from "./domain";
import type { OrderStore } from "./order-store";

const COLLECTION_NAME = "billingOrders";

function orderDocumentId(orderId: string): string {
  // Firestore document ids cannot contain "/" and are limited to 1500 bytes, so
  // escaping keeps a future id format from producing an invalid path.
  return encodeURIComponent(orderId);
}

function newestPaidFirst(left: Order, right: Order): number {
  return Date.parse(right.paidAt ?? "") - Date.parse(left.paidAt ?? "");
}

export class FirestoreOrderStore implements OrderStore {
  constructor(private readonly database: Firestore = getFirestore()) {}

  private reference(orderId: string) {
    return this.database.collection(COLLECTION_NAME).doc(orderDocumentId(orderId));
  }

  async create(order: Order): Promise<Order> {
    const reference = this.reference(order.id);
    // Transaction so a retried checkout cannot create two orders with one id.
    await this.database.runTransaction(async (transaction) => {
      const snapshot = await transaction.get(reference);
      if (snapshot.exists) return;
      transaction.create(reference, order);
    });
    return order;
  }

  async get(orderId: string): Promise<Order | null> {
    const snapshot = await this.reference(orderId).get();
    return snapshot.exists ? (snapshot.data() as Order) : null;
  }

  async findByIdempotencyKey(userId: string, idempotencyKey: string): Promise<Order | null> {
    const snapshot = await this.database
      .collection(COLLECTION_NAME)
      .where("userId", "==", userId)
      .where("idempotencyKey", "==", idempotencyKey)
      .get();
    return (snapshot.docs[0]?.data() as Order | undefined) ?? null;
  }

  async findPaidCredit(userId: string): Promise<Order | null> {
    const snapshot = await this.database
      .collection(COLLECTION_NAME)
      .where("userId", "==", userId)
      .get();
    return (
      snapshot.docs
        .map((entry: { data: () => DocumentData }) => entry.data() as Order)
        .filter((order: Order) => order.status === "paid")
        .sort(newestPaidFirst)[0] ?? null
    );
  }

  async update(order: Order): Promise<Order> {
    await this.reference(order.id).set(order, { merge: false });
    return order;
  }

  async consumeIfPaid(orderId: string, now: string): Promise<Order | null> {
    const reference = this.reference(orderId);
    return this.database.runTransaction(async (transaction) => {
      const snapshot = await transaction.get(reference);
      if (!snapshot.exists) return null;
      const order = snapshot.data() as Order;
      if (order.status !== "paid") return null;
      const consumed: Order = { ...order, status: "consumed", consumedAt: now, updatedAt: now };
      transaction.update(reference, consumed);
      return consumed;
    });
  }
}