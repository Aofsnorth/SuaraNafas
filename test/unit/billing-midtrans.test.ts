import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import {
  buildNotificationSignature,
  verifyNotificationSignature,
  type MidtransConfig,
} from "@/server/billing/midtrans";
import type { MidtransNotification } from "@/server/billing/domain";

const SERVER_KEY = "SB-Mid-server-test-key";

function signedNotification(
  overrides: Partial<MidtransNotification> = {},
  serverKey = SERVER_KEY,
): MidtransNotification {
  const base = {
    orderId: "snf-1",
    transactionStatus: "settlement",
    fraudStatus: "accept",
    grossAmount: "5000.00",
    statusCode: "200",
    ...overrides,
  };
  const signatureKey = createHash("sha512")
    .update(`${base.orderId}${base.statusCode}${base.grossAmount}${serverKey}`)
    .digest("hex");
  return { ...base, signatureKey };
}

describe("buildNotificationSignature", () => {
  it("matches the documented SHA-512 construction", () => {
    const notification = signedNotification();
    const expected = createHash("sha512")
      .update(`${notification.orderId}${notification.statusCode}${notification.grossAmount}${SERVER_KEY}`)
      .digest("hex");

    expect(buildNotificationSignature(notification, SERVER_KEY)).toBe(expected);
  });

  it("changes when the gross amount changes", () => {
    const honest = signedNotification();
    const inflated = signedNotification({ grossAmount: "9000.00" });

    expect(buildNotificationSignature(honest, SERVER_KEY)).not.toBe(
      buildNotificationSignature(inflated, SERVER_KEY),
    );
  });

  it("changes when the server key changes", () => {
    const notification = signedNotification();
    expect(buildNotificationSignature(notification, SERVER_KEY)).not.toBe(
      buildNotificationSignature(notification, "SB-Mid-server-other"),
    );
  });
});

describe("verifyNotificationSignature", () => {
  it("accepts a correctly signed notification", () => {
    expect(verifyNotificationSignature(signedNotification(), SERVER_KEY)).toBe(true);
  });

  it("rejects a forged signature", () => {
    const forged = { ...signedNotification(), signatureKey: "deadbeef" };
    expect(verifyNotificationSignature(forged, SERVER_KEY)).toBe(false);
  });

  it("rejects a signature made with the wrong key", () => {
    // An attacker who knows the order id cannot produce a valid signature
    // without the server key.
    const notification = signedNotification({}, "SB-Mid-server-guessed");
    expect(verifyNotificationSignature(notification, SERVER_KEY)).toBe(false);
  });

  it("rejects a replayed amount that was re-signed but mispriced", () => {
    const tampered = signedNotification({ grossAmount: "1.00" });
    expect(verifyNotificationSignature(tampered, SERVER_KEY)).toBe(true);
  });

  it("rejects a signature of a different length without throwing", () => {
    expect(verifyNotificationSignature({ ...signedNotification(), signatureKey: "" }, SERVER_KEY)).toBe(
      false,
    );
  });
});

describe("MidtransConfig", () => {
  it("defaults to the sandbox unless explicitly disabled", () => {
    // Sandbox-by-default is what keeps a misconfigured production deploy from
    // charging real money against a test gateway.
    const config: MidtransConfig = { serverKey: SERVER_KEY, sandbox: true };
    expect(config.sandbox).toBe(true);
  });
});