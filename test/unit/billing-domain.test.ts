import { describe, expect, it } from "vitest";

import {
  ANALYSIS_PRICE_IDR,
  BillingError,
  applyNotification,
  attachCharge,
  consumeOrder,
  createOrder,
  expireOrder,
  isPaidStatus,
  paymentStatus,
  type Order,
} from "@/server/billing/domain";

const NOW = "2026-10-03T10:00:00.000Z";

function newOrder(overrides: Partial<Order> = {}): Order {
  return {
    ...createOrder({
      id: "snf-test-1",
      userId: "user-1",
      email: "user@example.com",
      now: NOW,
      idempotencyKey: "key-abcdefgh",
      consentedToUnvalidatedCountry: true,
    }),
    ...overrides,
  };
}

describe("paymentStatus", () => {
  it("treats settlement and capture as paid", () => {
    expect(paymentStatus({ transactionStatus: "settlement", fraudStatus: "accept" })).toBe("paid");
    expect(paymentStatus({ transactionStatus: "capture", fraudStatus: "accept" })).toBe("paid");
  });

  it("treats a missing fraud_status as acceptable, per provider guidance", () => {
    expect(paymentStatus({ transactionStatus: "settlement", fraudStatus: undefined })).toBe("paid");
  });

  it("does not pay out when fraud status is challenged", () => {
    expect(paymentStatus({ transactionStatus: "settlement", fraudStatus: "challenge" })).toBe(
      "pending",
    );
  });

  it("never treats pending as paid", () => {
    expect(paymentStatus({ transactionStatus: "pending", fraudStatus: "accept" })).toBe("pending");
  });

  it("maps failure-like statuses to failed", () => {
    for (const status of ["expire", "deny", "cancel", "failure", "refund"]) {
      expect(paymentStatus({ transactionStatus: status, fraudStatus: undefined })).toBe("failed");
    }
  });

  it("is case-insensitive", () => {
    expect(paymentStatus({ transactionStatus: "SETTLEMENT", fraudStatus: "ACCEPT" })).toBe("paid");
  });
});

describe("applyNotification", () => {
  it("marks a pending order paid on settlement", () => {
    const updated = applyNotification(
      newOrder(),
      { transactionStatus: "settlement", fraudStatus: "accept" },
      NOW,
    );

    expect(updated.status).toBe("paid");
    expect(updated.paidAt).toBe(NOW);
  });

  it("is idempotent when the same settlement is delivered twice", () => {
    const order = newOrder();
    const once = applyNotification(order, { transactionStatus: "settlement" }, NOW);
    const twice = applyNotification(once, { transactionStatus: "settlement" }, NOW);

    expect(twice.status).toBe("paid");
    expect(twice.paidAt).toBe(once.paidAt);
  });

  it("does not downgrade a paid order when a late pending arrives", () => {
    const paid = applyNotification(newOrder(), { transactionStatus: "settlement" }, NOW);
    const afterLatePending = applyNotification(paid, { transactionStatus: "pending" }, NOW);

    expect(afterLatePending.status).toBe("paid");
  });

  it("does not consume a credit already spent", () => {
    const consumed: Order = {
      ...newOrder(),
      status: "consumed",
      consumedAt: NOW,
    };
    const updated = applyNotification(consumed, { transactionStatus: "expire" }, NOW);

    expect(updated.status).toBe("consumed");
    expect(updated.consumedAt).toBe(NOW);
  });

  it("expires an unpaid order that is still pending past its window", () => {
    const order = newOrder();
    const later = new Date(Date.parse(order.expiresAt) + 1_000).toISOString();

    expect(applyNotification(order, { transactionStatus: "pending" }, later).status).toBe("expired");
  });

  it("still records payment when funds settle after our expiry window", () => {
    const order = newOrder();
    const later = new Date(Date.parse(order.expiresAt) + 60_000).toISOString();
    const updated = applyNotification(order, { transactionStatus: "settlement" }, later);

    // The customer paid. The credit is owed even though our own clock ran out.
    expect(updated.status).toBe("paid");
  });

  it("marks a pending order failed on expiry", () => {
    expect(
      applyNotification(newOrder(), { transactionStatus: "expire" }, NOW).status,
    ).toBe("failed");
  });
});

describe("createOrder", () => {
  it("charges the configured screening price", () => {
    expect(newOrder().amountIdr).toBe(ANALYSIS_PRICE_IDR);
  });

  it("rejects a too-short idempotency key", () => {
    expect(() =>
      createOrder({
        id: "snf-1",
        userId: "u",
        email: null,
        now: NOW,
        idempotencyKey: "short",
        consentedToUnvalidatedCountry: false,
      }),
    ).toThrowError(BillingError);
  });

  it("starts pending with no QR attached yet", () => {
    const order = newOrder();
    expect(order.status).toBe("pending");
    expect(order.qrUrl).toBeNull();
    expect(order.transactionId).toBeNull();
  });

  it("records the consent flag on the order", () => {
    expect(newOrder().consentedToUnvalidatedCountry).toBe(true);
  });

  it("sets an expiry in the future", () => {
    expect(Date.parse(newOrder().expiresAt)).toBeGreaterThan(Date.parse(NOW));
  });
});

describe("consumeOrder", () => {
  it("spends a paid credit exactly once", () => {
    const consumed = consumeOrder(newOrder({ status: "paid" }), NOW);
    expect(consumed.status).toBe("consumed");
    expect(consumed.consumedAt).toBe(NOW);
  });

  it("refuses to consume an unpaid order", () => {
    expect(() => consumeOrder(newOrder(), NOW)).toThrowError(BillingError);
  });

  it("refuses to consume an already-consumed order", () => {
    expect(() => consumeOrder(newOrder({ status: "consumed" }), NOW)).toThrowError(BillingError);
  });
});

describe("expireOrder", () => {
  it("leaves a paid order alone", () => {
    const paid = newOrder({ status: "paid" });
    expect(expireOrder(paid, NOW).status).toBe("paid");
  });
});

describe("attachCharge", () => {
  it("stores the provider transaction and QR", () => {
    const updated = attachCharge(
      newOrder(),
      { transactionId: "tx-1", qrUrl: "https://api.sandbox.midtrans.com/qr" },
      NOW,
    );

    expect(updated.transactionId).toBe("tx-1");
    expect(updated.qrUrl).toBe("https://api.sandbox.midtrans.com/qr");
  });
});

describe("isPaidStatus", () => {
  it("covers paid and consumed, but not pending", () => {
    expect(isPaidStatus("paid")).toBe(true);
    expect(isPaidStatus("consumed")).toBe(true);
    expect(isPaidStatus("pending")).toBe(false);
    expect(isPaidStatus("failed")).toBe(false);
  });
});