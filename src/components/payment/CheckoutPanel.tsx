"use client";

import type { PaymentStage } from "@/hooks/usePayment";
import type { BillingConfig } from "@/services/payment-service";

function formatRupiah(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

interface CheckoutPanelProps {
  config: BillingConfig | null;
  stage: PaymentStage;
  qrUrl: string | null;
  error: string | null;
  acceptsUnvalidatedCountry: boolean;
  onConsentChange: (value: boolean) => void;
  onPay: () => void;
}

/**
 * Checkout surface shown before an analysis when billing is enabled.
 *
 * Renders nothing when screening is free, so the unpaid flow keeps exactly the
 * UI it had before payments existed. Payment state is owned by the parent, so
 * the credit id used for the analysis and this panel can never disagree.
 */
export function CheckoutPanel({
  config,
  stage,
  qrUrl,
  error,
  acceptsUnvalidatedCountry,
  onConsentChange,
  onPay,
}: CheckoutPanelProps) {
  if (stage === "loading" || stage === "not-required" || !config?.enabled) {
    return null;
  }

  return (
    <section className="panel checkout" aria-labelledby="checkout-heading">
      <h2 id="checkout-heading">Satu analisis, {formatRupiah(config.priceIdr)}</h2>

      {stage === "consent" && (
        <>
          <p className="helper-note">
            Pembayaran memberi Anda satu kali analisis rekaman batuk. Kredit hanya
            terpakai bila hasil analisis benar-benar keluar.
          </p>

          {/*
            Consent is required, not decorative: it is recorded on the order
            server-side and is the only thing that permits a score to be produced
            for a country the model was never validated on.
          */}
          <label className="field consent-box">
            <input
              type="checkbox"
              checked={acceptsUnvalidatedCountry}
              onChange={(event) => onConsentChange(event.target.checked)}
            />
            <span>
              Saya mengerti model ini belum divalidasi untuk peserta di Indonesia dan
              hasilnya bukan diagnosis. Saya tetap ingin memakai layanan eksperimental
              ini.
            </span>
          </label>

          <div className="form-actions mt-4">
            <button
              type="button"
              className="btn-primary"
              disabled={!acceptsUnvalidatedCountry}
              onClick={onPay}
            >
              Bayar {formatRupiah(config.priceIdr)}
            </button>
          </div>
          {!acceptsUnvalidatedCountry && (
            <p className="helper-note mt-2">
              Tandai persetujuan di atas untuk melanjutkan ke pembayaran.
            </p>
          )}
        </>
      )}

      {(stage === "paying" || stage === "pending") && (
        <div role="status" aria-live="polite">
          {qrUrl ? (
            <figure className="playback">
              {/*
                A plain img, not next/image: the QR is served from the payment
                provider's own host and the URL changes per order, so the
                optimizer would add a pointless proxy hop for a fixed-size code.
              */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrUrl}
                alt="Kode QRIS untuk pembayaran"
                width={220}
                height={220}
                className="checkout__qr"
              />
              <figcaption>
                Pindai dengan aplikasi apa pun yang mendukung QRIS. Status pembayaran
                diperiksa otomatis.
              </figcaption>
            </figure>
          ) : (
            <p className="helper-note">Menyiapkan kode pembayaran…</p>
          )}
        </div>
      )}

      {stage === "paid" && (
        <p role="status" aria-live="polite" className="chip chip--success">
          Pembayaran diterima. Lanjutkan rekaman dan kirim untuk analisis.
        </p>
      )}

      {stage === "failed" && (
        <div role="alert" className="recorder-workbench__error">
          <p>{error ?? "Pembayaran tidak berhasil."}</p>
        </div>
      )}
    </section>
  );
}