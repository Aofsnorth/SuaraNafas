"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchBillingConfig,
  newIdempotencyKey,
  startCheckout,
  waitForPayment,
  type BillingConfig,
} from "@/services/payment-service";

export type PaymentStage =
  | "loading"
  | "not-required"
  | "consent"
  | "paying"
  | "pending"
  | "paid"
  | "failed";

interface UsePaymentReturn {
  config: BillingConfig | null;
  stage: PaymentStage;
  qrUrl: string | null;
  orderId: string | null;
  error: string | null;
  acceptsUnvalidatedCountry: boolean;
  setAcceptsUnvalidatedCountry: (value: boolean) => void;
  beginCheckout: () => Promise<void>;
  /** Order id to attach to an analysis request, once a credit is available. */
  creditOrderId: string | null;
  reset: () => void;
}

/**
 * Drives the paywall for one screening session.
 *
 * Billing is treated as optional infrastructure: if the config cannot be read,
 * the stage resolves to "not-required" and screening proceeds free rather than
 * blocking a user over a payment outage.
 */
export function usePayment(): UsePaymentReturn {
  const [config, setConfig] = useState<BillingConfig | null>(null);
  const [stage, setStage] = useState<PaymentStage>("loading");
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acceptsUnvalidatedCountry, setAcceptsUnvalidatedCountry] = useState(false);

  useEffect(() => {
    let active = true;
    void fetchBillingConfig().then((loaded) => {
      if (!active) return;
      setConfig(loaded);
      setStage(loaded?.enabled ? "consent" : "not-required");
    });
    return () => {
      active = false;
    };
  }, []);

  const beginCheckout = useCallback(async () => {
    if (!config?.enabled) {
      setStage("not-required");
      return;
    }

    setError(null);
    setStage("paying");
    // One key per attempt: a retried or double-tapped pay button must reuse the
    // same order rather than creating a second charge.
    const key = newIdempotencyKey();

    try {
      const session = await startCheckout({
        acceptsUnvalidatedCountry,
        idempotencyKey: key,
      });
      setOrderId(session.orderId);
      setQrUrl(session.qrUrl);

      if (session.status !== "pending") {
        setStage(session.status === "paid" || session.status === "consumed" ? "paid" : "failed");
        return;
      }

      setStage("pending");
      const status = await waitForPayment(session.orderId);
      setStage(status === "paid" ? "paid" : "failed");
      if (status !== "paid") {
        setError(
          status === "expired"
            ? "Kode QRIS sudah kedaluwarsa. Buat pesanan baru untuk melanjutkan."
            : "Pembayaran tidak berhasil. Silakan coba lagi.",
        );
      }
    } catch (caught) {
      setStage("failed");
      setError(caught instanceof Error ? caught.message : "Pembayaran gagal diproses.");
    }
  }, [acceptsUnvalidatedCountry, config?.enabled]);

  const reset = useCallback(() => {
    setError(null);
    setQrUrl(null);
    setOrderId(null);
    setStage(config?.enabled ? "consent" : "not-required");
  }, [config?.enabled]);

  return {
    config,
    stage,
    qrUrl,
    orderId,
    error,
    acceptsUnvalidatedCountry,
    setAcceptsUnvalidatedCountry,
    beginCheckout,
    creditOrderId: stage === "paid" ? orderId : null,
    reset,
  };
}