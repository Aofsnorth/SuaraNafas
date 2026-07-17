"use client";

import { Modal } from "@/components/ui/modal";
import { ConvexSurface } from "@/components/convex-surface";
import { AnalysisResult } from "@/lib/types";
import { ScoreBars } from "@/components/result/ScoreBars";
import { SpectrogramView } from "@/components/result/SpectrogramView";

interface ResultDetailProps {
  open: boolean;
  result: AnalysisResult | null;
  onClose: () => void;
  onAnalyzeAi: () => void;
}

export function ResultDetail({ open, result, onClose, onAnalyzeAi }: ResultDetailProps) {
  const detail = result?.detail;

  return (
    <Modal
      open={open}
      onClose={onClose}
      labelledBy="result-detail-title"
      className="overlay overlay--detail"
    >
      <ConvexSurface variant="panel" className="overlay__panel overlay__panel--wide">
        <div className="overlay__badges">
          <span className="recorder-result__mode">Nilai simulasi</span>
          {detail?.model ? (
            <span className="overlay__model">
              {detail.model.name} · {detail.model.version} · {detail.model.durationMs} ms
            </span>
          ) : null}
        </div>
        <h2 id="result-detail-title" className="overlay__title">
          Detail keluaran model (simulasi)
        </h2>
        <p className="overlay__body">
          Angka berikut adalah nilai simulasi untuk memperagakan antarmuka, bukan
          probabilitas klinis.
        </p>

        {detail ? (
          <>
            <ScoreBars scores={detail.scores} />

            {detail.spectrogram ? (
              <div className="overlay__section">
                <p className="section-tag">Spektrogram simulasi</p>
                <SpectrogramView matrix={detail.spectrogram} />
              </div>
            ) : null}

            {detail.features ? (
              <dl className="feature-list">
                {detail.features.map((feature) => (
                  <div key={feature.label}>
                    <dt>{feature.label}</dt>
                    <dd>{feature.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </>
        ) : (
          <p className="overlay__body">Detail simulasi tidak tersedia.</p>
        )}

        <div className="overlay__actions">
          <button type="button" className="btn-outline" onClick={onClose}>
            Tutup
          </button>
          <button type="button" className="btn-primary" onClick={onAnalyzeAi}>
            Analisis dengan AI
          </button>
        </div>
      </ConvexSurface>
    </Modal>
  );
}
