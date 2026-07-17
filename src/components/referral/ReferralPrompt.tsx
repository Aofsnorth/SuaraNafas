"use client";

import { ConvexSurface } from "@/components/convex-surface";

interface ReferralPromptProps {
  scenarioLabel: string;
  onClose: () => void;
  onRefer: () => void;
  onDetail: () => void;
}

export function ReferralPrompt({
  scenarioLabel,
  onClose,
  onRefer,
  onDetail,
}: ReferralPromptProps) {
  return (
    <ConvexSurface
      variant="panel"
      className="w-full flex flex-col justify-between p-6 md:p-8"
      aria-labelledby="referral-prompt-title"
    >
      <div>
        <p className="section-tag">{scenarioLabel} · nilai simulasi</p>
        <h2 id="referral-prompt-title" className="text-xl md:text-2xl font-heading mb-4 mt-2">
          Langkah lanjutan
        </h2>
        <p className="text-ink-2 leading-relaxed text-sm md:text-base max-w-[52ch]">
          Simulasi antarmuka menandai skenario ini. Ini bukan diagnosis medis.
          Anda dapat meninjau rekomendasi dokter atau melihat detail keluaran
          simulasi.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-6">
        <button type="button" className="btn-outline" onClick={onClose}>
          Tutup
        </button>
        <button type="button" className="btn-primary" onClick={onRefer}>
          Rujuk
        </button>
        <button type="button" className="cta-link animate-pulse" onClick={onDetail}>
          Detail hasil →
        </button>
      </div>
    </ConvexSurface>
  );
}
