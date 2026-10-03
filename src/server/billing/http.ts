import { randomUUID } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

import { resolveCaller } from "@/server/auth/identity";
import { BillingError, OrderNotFoundError } from "./domain";

const MAX_IDEMPOTENCY_KEY_LENGTH = 128;

export function jsonError(code: string, message: string, status: number): NextResponse {
  return NextResponse.json({ error: message, code }, { status });
}

/**
 * Guard shared by every billing route.
 *
 * Refuses in three distinct situations rather than guessing: no Firebase admin
 * credentials (the environment is not ready to verify identity), no request
 * token, or an invalid token. All three mean "not authorised".
 */
export async function requireCaller(request: NextRequest): Promise<
  { error: NextResponse } | { caller: { uid: string; email: string | null } }
> {
  const caller = await resolveCaller(request.headers.get("authorization"));
  if (!caller) {
    return { error: jsonError("UNAUTHENTICATED", "Silakan masuk untuk melanjutkan.", 401) };
  }
  return { caller };
}

export function billingErrorResponse(error: unknown): NextResponse {
  if (error instanceof OrderNotFoundError || error instanceof BillingError) {
    return jsonError(error.code, error.message, error.status);
  }
  return jsonError("BILLING_ERROR", "Pembayaran tidak dapat diproses saat ini.", 500);
}

export function readIdempotencyKey(request: NextRequest): string | null {
  const key = request.headers.get("idempotency-key")?.trim();
  if (!key || key.length > MAX_IDEMPOTENCY_KEY_LENGTH) return null;
  return key;
}

export function generateOrderId(): string {
  return `snf-${randomUUID()}`;
}