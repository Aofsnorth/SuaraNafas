import { createHash, timingSafeEqual } from "node:crypto";

import {
  BillingError,
  type MidtransChargeRequest,
  type MidtransChargeResult,
  type MidtransNotification,
} from "./domain";

const SANDBOX_BASE_URL = "https://api.sandbox.midtrans.com";
const PRODUCTION_BASE_URL = "https://api.midtrans.com";
const CHARGE_PATH = "/v2/charge";
const STATUS_PATH_SUFFIX = "/status";
const REQUEST_TIMEOUT_MS = 15_000;

export interface MidtransConfig {
  serverKey: string;
  sandbox: boolean;
}

export function readMidtransConfig(env: NodeJS.ProcessEnv = process.env): MidtransConfig | null {
  const serverKey = env.MIDTRANS_SERVER_KEY?.trim();
  if (!serverKey) return null;
  return { serverKey, sandbox: env.MIDTRANS_SANDBOX !== "false" };
}

function baseUrl(config: MidtransConfig): string {
  return config.sandbox ? SANDBOX_BASE_URL : PRODUCTION_BASE_URL;
}

function authorizationHeader(config: MidtransConfig): string {
  return `Basic ${Buffer.from(`${config.serverKey}:`).toString("base64")}`;
}

/**
 * Midtrans signs notifications as SHA512(order_id + status_code +
 * gross_amount + server_key). The server key never leaves the server, so this
 * comparison is the only thing that distinguishes a real settlement from a
 * forged POST to the webhook.
 */
export function buildNotificationSignature(
  notification: Pick<MidtransNotification, "orderId" | "statusCode" | "grossAmount">,
  serverKey: string,
): string {
  const payload = `${notification.orderId}${notification.statusCode}${notification.grossAmount}${serverKey}`;
  return createHash("sha512").update(payload).digest("hex");
}

export function verifyNotificationSignature(
  notification: MidtransNotification,
  serverKey: string,
): boolean {
  const expected = buildNotificationSignature(notification, serverKey);
  const received = notification.signatureKey;
  if (expected.length !== received.length) return false;
  return timingSafeEqual(Buffer.from(expected), Buffer.from(received));
}

function parseChargeResponse(payload: unknown): MidtransChargeResult {
  if (typeof payload !== "object" || payload === null) {
    throw new BillingError("PAYMENT_PROVIDER_INVALID", "Respons pembayaran tidak valid.", 502);
  }
  const body = payload as Record<string, unknown>;
  const transactionId = body.transaction_id;
  const actions = body.actions;

  if (typeof transactionId !== "string" || !Array.isArray(actions)) {
    throw new BillingError("PAYMENT_PROVIDER_INVALID", "Respons pembayaran tidak lengkap.", 502);
  }

  const qrAction = actions.find((action) => {
    if (typeof action !== "object" || action === null) return false;
    const record = action as Record<string, unknown>;
    return record.name === "generate-qr-code" && typeof record.url === "string";
  }) as { url?: unknown } | undefined;

  if (typeof qrAction?.url !== "string" || !qrAction.url.startsWith("https://")) {
    throw new BillingError("PAYMENT_PROVIDER_INVALID", "QR pembayaran tidak tersedia.", 502);
  }

  return { transactionId, qrUrl: qrAction.url };
}

/**
 * Request a static QRIS charge.
 *
 * A provider failure must surface as an error rather than a fabricated order:
 * the user has not been charged, so they must not be told a QR exists.
 */
export async function createQrisCharge(
  config: MidtransConfig,
  request: MidtransChargeRequest,
): Promise<MidtransChargeResult> {
  const body = {
    payment_type: "qris",
    transaction_details: {
      order_id: request.orderId,
      gross_amount: request.grossAmount,
    },
    item_details: [
      {
        id: "screening-audio",
        price: request.grossAmount,
        quantity: 1,
        name: "Analisis rekaman batuk (prototipe riset)",
      },
    ],
    ...(request.email ? { customer_details: { email: request.email } } : {}),
    qris: { acquirer: "gopay" },
  };

  const response = await fetch(`${baseUrl(config)}${CHARGE_PATH}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: authorizationHeader(config),
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new BillingError(
      "PAYMENT_PROVIDER_ERROR",
      "Layanan pembayaran sedang tidak tersedia. Coba lagi sebentar.",
      502,
    );
  }

  return parseChargeResponse(await response.json());
}

function parseStatusResponse(payload: unknown): {
  transactionStatus: string;
  fraudStatus?: string;
} {
  if (typeof payload !== "object" || payload === null) {
    throw new BillingError("PAYMENT_PROVIDER_INVALID", "Status pembayaran tidak valid.", 502);
  }
  const body = payload as Record<string, unknown>;
  const transactionStatus = body.transaction_status;
  if (typeof transactionStatus !== "string") {
    throw new BillingError("PAYMENT_PROVIDER_INVALID", "Status pembayaran tidak lengkap.", 502);
  }
  return {
    transactionStatus,
    ...(typeof body.fraud_status === "string" ? { fraudStatus: body.fraud_status } : {}),
  };
}

/**
 * Ask Midtrans directly whether a transaction settled.
 *
 * This is the fallback for a missed webhook: Midtrans documents that HTTP
 * notifications can be delayed or retried, so the client polls status through
 * the app rather than trusting a notification that may never arrive.
 */
export async function fetchTransactionStatus(
  config: MidtransConfig,
  orderId: string,
): Promise<{ transactionStatus: string; fraudStatus?: string }> {
  const response = await fetch(
    `${baseUrl(config)}/v2/${encodeURIComponent(orderId)}${STATUS_PATH_SUFFIX}`,
    {
      headers: {
        Accept: "application/json",
        Authorization: authorizationHeader(config),
      },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      cache: "no-store",
    },
  );

  if (response.status === 404) {
    return { transactionStatus: "pending", fraudStatus: undefined };
  }
  if (!response.ok) {
    throw new BillingError(
      "PAYMENT_PROVIDER_ERROR",
      "Status pembayaran tidak dapat dikonfirmasi.",
      502,
    );
  }

  return parseStatusResponse(await response.json());
}