import { NextResponse, type NextRequest } from "next/server";

import { resolveBillingService } from "@/server/billing/container";
import { billingErrorResponse, jsonError, requireCaller } from "@/server/billing/http";

export const runtime = "nodejs";

const MAX_ORDER_ID_LENGTH = 128;

/**
 * Order status for its owner.
 *
 * The lookup is scoped to the caller's uid, so a guessed order id reveals
 * nothing: another user's order is reported as not found rather than
 * forbidden, which also avoids confirming that it exists.
 *
 * The stored status is returned as-is. Reconciliation with the provider lives
 * in the service so the webhook and this route can never disagree about what
 * "paid" means.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ orderId: string }> },
) {
  const billing = resolveBillingService();
  if (!billing) {
    return jsonError("BILLING_UNAVAILABLE", "Pembayaran belum dikonfigurasi.", 503);
  }

  const auth = await requireCaller(request);
  if ("error" in auth) return auth.error;

  const { orderId } = await params;
  if (!orderId || orderId.length > MAX_ORDER_ID_LENGTH) {
    return jsonError("ORDER_NOT_FOUND", "Order tidak ditemukan.", 404);
  }

  try {
    const order = await billing.service.getOrderForUser(orderId, auth.caller.uid);
    return NextResponse.json({
      orderId: order.id,
      status: order.status,
      amountIdr: order.amountIdr,
      currency: "IDR",
      expiresAt: order.expiresAt,
    });
  } catch (error) {
    return billingErrorResponse(error);
  }
}