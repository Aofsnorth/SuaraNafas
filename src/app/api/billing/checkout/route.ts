import { NextResponse, type NextRequest } from "next/server";

import { resolveBillingService } from "@/server/billing/container";
import { PUBLIC_BILLING_CONFIG } from "@/server/billing/config";
import { ANALYSIS_PRICE_IDR } from "@/server/billing/domain";
import {
  billingErrorResponse,
  jsonError,
  readIdempotencyKey,
  requireCaller,
} from "@/server/billing/http";

export const runtime = "nodejs";

const UNCONFIGURED_MESSAGE =
  "Pembayaran belum dikonfigurasi. Analisis tetap tersedia tanpa biaya.";

/**
 * Read the unvalidated-country consent from the request body.
 *
 * Consenting is mandatory whenever the buyer could ever be scored for a country
 * outside the model's training data, because that consent is what later permits
 * an experimental score to be produced at all.
 */
async function readConsent(
  request: NextRequest,
): Promise<{ error: NextResponse } | { accepted: boolean }> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return { error: jsonError("INVALID_BODY", "Permintaan pembayaran tidak valid.", 400) };
  }
  if (typeof body !== "object" || body === null) {
    return { error: jsonError("INVALID_BODY", "Permintaan pembayaran tidak valid.", 400) };
  }
  const consent = (body as Record<string, unknown>).acceptsUnvalidatedCountry;
  if (consent !== true && consent !== false) {
    return {
      error: jsonError(
        "CONSENT_REQUIRED",
        "Anda harus menyetujui condition sebelum membayar.",
        400,
      ),
    };
  }
  return { accepted: consent };
}

export async function POST(request: NextRequest) {
  const billing = resolveBillingService();
  if (!billing) {
    return jsonError("BILLING_UNAVAILABLE", UNCONFIGURED_MESSAGE, 503);
  }

  const auth = await requireCaller(request);
  if ("error" in auth) return auth.error;

  const idempotencyKey = readIdempotencyKey(request);
  if (!idempotencyKey) {
    return jsonError(
      "MISSING_IDEMPOTENCY_KEY",
      "Permintaan pembayaran tidak lengkap. Muat ulang halaman lalu coba lagi.",
      400,
    );
  }

  const consented = await readConsent(request);
  if ("error" in consented) return consented.error;

  try {
    const order = await billing.service.startCheckout({
      userId: auth.caller.uid,
      email: auth.caller.email,
      idempotencyKey,
      consentedToUnvalidatedCountry: consented.accepted,
    });

    return NextResponse.json(
      {
        orderId: order.id,
        status: order.status,
        amountIdr: order.amountIdr,
        currency: "IDR",
        qrUrl: order.qrUrl,
        expiresAt: order.expiresAt,
      },
      { status: order.status === "pending" ? 201 : 200 },
    );
  } catch (error) {
    return billingErrorResponse(error);
  }
}

/** Tells the client whether checkout exists and what a screening costs. */
export async function GET() {
  return NextResponse.json({
    enabled: Boolean(resolveBillingService()) && PUBLIC_BILLING_CONFIG.enabled,
    priceIdr: ANALYSIS_PRICE_IDR,
    currency: "IDR",
    sandbox: PUBLIC_BILLING_CONFIG.sandbox,
    unvalidatedCountries: PUBLIC_BILLING_CONFIG.unvalidatedCountries,
  });
}