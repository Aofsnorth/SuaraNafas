"use client";

import { Modal } from "@/components/ui/modal";
import { ConvexSurface } from "@/components/convex-surface";

interface ReferralPromptProps {
  open: boolean;
  scenarioLabel: string;
  onClose: () => void;
  onRefer: () => void;
  onDetail: () => void;
}

export function ReferralPrompt({
  open,
  scenarioLabel,
  onClose,
  onRefer,
  onDetail,
}: ReferralPromptProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      labelledBy="referral-prompt-title"
      className="overlay overlay--prompt"
    >
      <ConvexSurface variant="panel" className="overlay__panel">
        <p className="section-tag">{scenarioLabel} · nilai simulasi</p>
        <h2 id="referral-prompt-title" className="overlay__title">
          Langkah lanjutan
        </h2>
        <p className="overlay__body">
          Simulasi antarmuka menandai skenario ini. Ini bukan diagnosis medis.
          Anda dapat meninjau rekomendasi dokter atau melihat detail keluaran
          simulasi.
        </p>
        <div className="overlay__actions">
          <button type="button" className="btn-outline" onClick={onClose}>
            Tutup
          </button>
          <button type="button" className="btn-primary" onClick={onRefer}>
            Rujuk
          </button>
          <button type="button" className="cta-link" onClick={onDetail}>
            Detail hasil →
          </button>
        </div>
      </ConvexSurface>
    </Modal>
  );
}
