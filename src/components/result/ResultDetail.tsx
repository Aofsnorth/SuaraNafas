"use client";

import { ConvexSurface } from "@/components/convex-surface";
import { AnalysisResult } from "@/lib/types";
import { ScoreBars } from "@/components/result/ScoreBars";
import { SpectrogramView } from "@/components/result/SpectrogramView";

interface ResultDetailProps {
  result: AnalysisResult | null;
  onClose: () => void;
  onAnalyzeAi: () => void;
}

export function ResultDetail({ result, onClose, onAnalyzeAi }: ResultDetailProps) {
  const detail = result?.detail;
  const isMockResult = result?.source === "mock";

  return (
    <ConvexSurface
      variant="panel"
      className="result-detail-card w-full flex flex-col justify-between p-5 md:p-6"
      aria-labelledby="result-detail-title"
    >
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <span className="recorder-result__mode">
            {isMockResult ? "Prediksi simulasi" : "Model CNN"}
          </span>
          {detail?.model ? (
            <span className="font-mono text-xs text-muted">
              {detail.model.name} · {detail.model.version} · {detail.model.durationMs} ms
            </span>
          ) : null}
        </div>
        <h2 id="result-detail-title" className="text-xl md:text-2xl font-heading mb-2">
          Detail analisis audio
        </h2>
        <p className="text-ink-2 leading-relaxed text-sm max-w-[58ch] mb-4">
          {isMockResult
            ? "Prediksi risiko masih simulasi. Spektrogram di bawah dihitung dari audio yang benar-benar direkam atau diunggah."
            : "Prediksi berasal dari backend CNN. Spektrogram menampilkan karakter frekuensi audio yang dikirim."}
        </p>

        {detail ? (
          <div className="space-y-4">
            <ScoreBars scores={detail.scores} />

            {detail.spectrogram ? (
              <div>
                <p className="section-tag mb-2">
                  {detail.spectrogramSource === "audio"
                    ? "Spektrogram audio aktual"
                    : "Spektrogram backend"}
                </p>
                <SpectrogramView
                  matrix={detail.spectrogram}
                  source={detail.spectrogramSource}
                />
              </div>
            ) : null}

            {detail.features ? (
              <dl className="feature-list mt-4">
                {detail.features.map((feature) => (
                  <div key={feature.label}>
                    <dt>{feature.label}</dt>
                    <dd>{feature.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>
        ) : (
          <p className="text-ink-2">Detail analisis tidak tersedia.</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 mt-5 pt-4 border-t border-rule">
        <button type="button" className="btn-outline" onClick={onClose}>
          Kembali
        </button>
        <button type="button" className="btn-primary" onClick={onAnalyzeAi}>
          Analisis dengan AI
        </button>
      </div>
    </ConvexSurface>
  );
}
