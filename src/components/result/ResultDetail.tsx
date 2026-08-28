"use client";

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
    <section className="panel result-detail" aria-labelledby="result-detail-title">
      <div>
        <div className="result-detail__badges">
          <span className={isMockResult ? "chip chip--demo" : "chip"}>
            {isMockResult ? "Prediksi simulasi" : "Model CNN"}
          </span>
          {detail?.model ? (
            <span className="model-meta">
              {detail.model.name} · {detail.model.version} · {detail.model.durationMs} ms
            </span>
          ) : null}
        </div>

        <h2 id="result-detail-title">Detail analisis audio</h2>
        <p className="result-detail__intro">
          {isMockResult
            ? "Prediksi risiko masih simulasi — audio tidak dianalisis. Spektrogram di bawah dihitung dari rekaman asli Anda, jadi tetap bisa dipakai memahami cara kerja model."
            : "Prediksi berasal dari backend CNN. Spektrogram menampilkan karakter frekuensi dari audio yang dikirim."}
        </p>

        {detail ? (
          <div className="space-y-5">
            <ScoreBars scores={detail.scores} />

            {detail.spectrogram ? (
              <div>
                <p className="spectrogram-label">
                  {detail.spectrogramSource === "audio"
                    ? "Spektrogram rekaman Anda"
                    : "Spektrogram backend"}
                </p>
                <SpectrogramView
                  matrix={detail.spectrogram}
                  source={detail.spectrogramSource}
                />
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
          </div>
        ) : (
          <p className="result-detail__intro">Detail analisis tidak tersedia.</p>
        )}
      </div>

      <div className="result-detail__actions">
        <button type="button" className="btn-outline" onClick={onClose}>
          Kembali
        </button>
        <button type="button" className="btn-primary" onClick={onAnalyzeAi}>
          Tanya asisten AI
        </button>
      </div>
    </section>
  );
}
