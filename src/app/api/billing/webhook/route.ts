import { NextResponse, type NextRequest } from "next/server";

import { resolveBillingService } from "@/server/billing/container";
import type { MidtransNotification } from "@/server/billing/domain";
import { OrderNotFoundError } from "@/server/billing/domain";
import { readMidtransConfig, verifyNotificationSignature } from "@/server/billing/midtrans";

export const runtime = "nodejs";

/** Parse a provider amount into integer rupiah. */
function parseAmount(value: string): number | null {
  const normalized = value.replace(/,/g, "").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  return Math.round(Number.parseFloat(normalized));
}

function readNotification(payload: Record<string, unknown>): MidtransNotification | null {
  const notification: MidtransNotification = {
    orderId: typeof payload.order_id === "string" ? payload.order_id : "",
    transactionStatus: typeof payload.transaction_status === "string" ? payload.transaction_status : "",
    fraudStatus: typeof payload.fraud_status === "string" ? payload.fraud_status : undefined,
    grossAmount: typeof payload.gross_amount === "string" ? payload.gross_amount : "",
    statusCode: typeof payload.status_code === "string" ? payload.status_code : "",
    signatureKey: typeof payload.signature_key === "string" ? payload.signature_key : "",
  };

  const complete =
    notification.orderId &&
    notification.transactionStatus &&
    notification.grossAmount &&
    notification.statusCode &&
    notification.signatureKey;
  return complete ? notification : null;
}

/**
 * Midtrans HTTP notification endpoint.
 *
 * Two independent checks must pass before an order is marked paid: the SHA-512
 * signature over the server key, and a match against our own stored order at
 * the expected amount. A body that claims a different gross amount than we
 * charged is rejected rather than absorbed — it means the provider settled
 * something we did not ask for.
 *
 * Response codes follow Midtrans' retry policy: 2xx stops retries, 400 retries
 * twice, 503 retries four times. A store failure must therefore never answer
 * 200, otherwise a settled payment would be silently dropped.
 */
export async function POST(request: NextRequest) {
  const billing = resolveBillingService();
  const config = readMidtransConfig();
  if (!billing || !config) {
    return NextResponse.json({ error: "Billing not configured" }, { status: 503 });
  }

  let payload: Record<string, unknown>;
  try {
    payload = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Malformed notification" }, { status: 400 });
  }

  const notification = readNotification(payload);
  if (!notification) {
    return NextResponse.json({ error: "Incomplete notification" }, { status: 400 });
  }

  if (!verifyNotificationSignature(notification, config.serverKey)) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  let storedAmount: number | null = null;
  try {
    const order = await billing.store.get(notification.orderId);
    if (!order) {
      // Retrying an unknown order will never succeed; 400 asks Midtrans to try
      // twice and then leave it in the dashboard for reconciliation.
      return NextResponse.json({ error: "Unknown order" }, { status: 400 });
    }
    storedAmount = order.amountIdr;
  } catch {
    return NextResponse.json({ error: "Order store unavailable" }, { status: 503 });
  }

  if (parseAmount(notification.grossAmount) !== storedAmount) {
    return NextResponse.json({ error: "Amount mismatch" }, { status: 400 });
  }

  try {
    await billing.service.handleNotification({
      orderId: notification.orderId,
      transactionStatus: notification.transactionStatus,
      fraudStatus: notification.fraudStatus,
    });
  } catch (error) {
    if (error instanceof OrderNotFoundError) {
      return NextResponse.json({ error: "Unknown order" }, { status: 400 });
    }
    return NextResponse.json({ error: "Webhook processing failed" }, { status: 503 });
  }

  return NextResponse.json({ received: true });
}