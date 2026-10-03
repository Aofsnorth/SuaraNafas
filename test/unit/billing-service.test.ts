import { describe, expect, it, vi } from "vitest";

import { ANALYSIS_PRICE_IDR, BillingError, type Order } from "@/server/billing/domain";
import { InMemoryOrderStore } from "@/server/billing/order-store";
import {
  BillingService,
  type BillingGateway,
} from "@/server/billing/service";

const NOW = new Date("2026-10-03T10:00:00.000Z");

function makeService(overrides: {
  gateway?: Partial<BillingGateway>;
  now?: Date;
} = {}) {
  const store = new InMemoryOrderStore();
  const gateway: BillingGateway = {
    chargeQris: vi.fn(async () => ({
      transactionId: "tx-1",
      qrUrl: "https://api.sandbox.midtrans.com/qr",
    })),
    transactionStatus: vi.fn(async () => ({
      transactionStatus: "pending",
      fraudStatus: undefined as string | undefined,
    })),
    ...overrides.gateway,
  };

  let counter = 0;
  const service = new BillingService({
    store,
    gateway,
    now: () => overrides.now ?? NOW,
    generateOrderId: () => `snf-${++counter}`,
  });

  return { service, store, gateway };
}

const checkoutInput = {
  userId: "user-1",
  email: "user@example.com",
  idempotencyKey: "key-abcdefgh",
  consentedToUnvalidatedCountry: true,
};

describe("startCheckout", () => {
  it("creates a pending order with a QR", async () => {
    const { service } = makeService();
    const order = await service.startCheckout(checkoutInput);

    expect(order.status).toBe("pending");
    expect(order.qrUrl).toBe("https://api.sandbox.midtrans.com/qr");
    expect(order.amountIdr).toBe(ANALYSIS_PRICE_IDR);
  });

  it("charges the stored price, not a client-supplied one", async () => {
    const { service, gateway } = makeService();
    await service.startCheckout(checkoutInput);

    expect(gateway.chargeQris).toHaveBeenCalledWith({
      orderId: "snf-1",
      grossAmount: ANALYSIS_PRICE_IDR,
      email: "user@example.com",
    });
  });

  it("is idempotent for a replayed key: no second charge", async () => {
    const { service, gateway } = makeService();
    const first = await service.startCheckout(checkoutInput);
    const second = await service.startCheckout(checkoutInput);

    expect(second.id).toBe(first.id);
    expect(gateway.chargeQris).toHaveBeenCalledTimes(1);
  });

  it("scopes idempotency per user, so two users can both check out", async () => {
    const { service } = makeService();
    await service.startCheckout(checkoutInput);
    const other = await service.startCheckout({ ...checkoutInput, userId: "user-2" });

    expect(other.id).not.toBe("snf-1");
  });

  it("fails the order when the provider charge fails", async () => {
    const { service, store } = makeService({
      gateway: {
        chargeQris: vi.fn(async () => {
          throw new BillingError("PAYMENT_PROVIDER_ERROR", "gateway down", 502);
        }),
      },
    });

    await expect(service.startCheckout(checkoutInput)).rejects.toThrow(BillingError);
    const stored = await store.get("snf-1");
    // No money moved, so the row must not linger as a payable pending order.
    expect(stored?.status).toBe("failed");
  });
});

describe("getOrderForUser", () => {
  it("returns the order to its owner", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);

    const found = await service.getOrderForUser(created.id, "user-1");
    expect(found.id).toBe(created.id);
  });

  it("hides another user's order behind a not-found", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);

    await expect(service.getOrderForUser(created.id, "user-2")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("reports a settlement the webhook missed", async () => {
    const { service } = makeService({
      gateway: {
        transactionStatus: vi.fn(async () => ({
          transactionStatus: "settlement",
          fraudStatus: "accept",
        })),
      },
    });
    const created = await service.startCheckout(checkoutInput);

    const reconciled = await service.getOrderForUser(created.id, "user-1");
    expect(reconciled.status).toBe("paid");
  });

  it("keeps the known state when the provider is unreachable", async () => {
    const { service } = makeService({
      gateway: {
        transactionStatus: vi.fn(async () => {
          throw new BillingError("PAYMENT_PROVIDER_ERROR", "down", 502);
        }),
      },
    });
    const created = await service.startCheckout(checkoutInput);

    const order = await service.getOrderForUser(created.id, "user-1");
    expect(order.status).toBe("pending");
  });
});

describe("consumeCredit", () => {
  async function paidOrder(): Promise<{ service: BillingService; order: Order }> {
    const context = makeService({
      gateway: {
        transactionStatus: vi.fn(async () => ({
          transactionStatus: "settlement",
          fraudStatus: "accept",
        })),
      },
    });
    const created = await context.service.startCheckout(checkoutInput);
    const paid = await context.service.handleNotification({
      orderId: created.id,
      transactionStatus: "settlement",
      fraudStatus: "accept",
    });
    return { service: context.service, order: paid };
  }

  it("spends a paid credit", async () => {
    const { service, order } = await paidOrder();
    const consumed = await service.consumeCredit("user-1", order.id);

    expect(consumed.status).toBe("consumed");
  });

  it("cannot be spent twice", async () => {
    const { service, order } = await paidOrder();
    await service.consumeCredit("user-1", order.id);

    await expect(service.consumeCredit("user-1", order.id)).rejects.toMatchObject({
      status: 404,
    });
  });

  it("refuses a credit belonging to somebody else", async () => {
    const { service, order } = await paidOrder();
    await expect(service.consumeCredit("user-2", order.id)).rejects.toMatchObject({
      status: 404,
    });
  });

  it("refuses when no order id is supplied", async () => {
    const { service } = await paidOrder();
    await expect(service.consumeCredit("user-1", null)).rejects.toMatchObject({ status: 404 });
  });

  it("refuses an unpaid order", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);

    await expect(service.consumeCredit("user-1", created.id)).rejects.toMatchObject({
      status: 404,
    });
  });
});

describe("handleNotification", () => {
  it("rejects an unknown order rather than inventing one", async () => {
    const { service } = makeService();
    await expect(
      service.handleNotification({ orderId: "snf-missing", transactionStatus: "settlement" }),
    ).rejects.toMatchObject({ status: 404 });
  });

  it("marks a paid order settled without changing it again", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);

    const settled = await service.handleNotification({
      orderId: created.id,
      transactionStatus: "settlement",
      fraudStatus: "accept",
    });
    const replay = await service.handleNotification({
      orderId: created.id,
      transactionStatus: "settlement",
      fraudStatus: "accept",
    });

    expect(replay.status).toBe("paid");
    expect(replay.paidAt).toBe(settled.paidAt);
  });
});

describe("getAvailableCredit", () => {
  it("returns nothing when the user never paid", async () => {
    const { service } = makeService();
    expect(await service.getAvailableCredit("user-1")).toBeNull();
  });

  it("returns the paid credit for the user", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);
    await service.handleNotification({
      orderId: created.id,
      transactionStatus: "settlement",
      fraudStatus: "accept",
    });

    expect((await service.getAvailableCredit("user-1"))?.id).toBe(created.id);
  });

  it("stops offering a credit that was already spent", async () => {
    const { service } = makeService();
    const created = await service.startCheckout(checkoutInput);
    await service.handleNotification({
      orderId: created.id,
      transactionStatus: "settlement",
      fraudStatus: "accept",
    });
    await service.consumeCredit("user-1", created.id);

    expect(await service.getAvailableCredit("user-1")).toBeNull();
  });
});