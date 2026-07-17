"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAnalysis } from "@/hooks/useAnalysis";
import { useResultFlow } from "@/hooks/useResultFlow";
import { LiveWaveform } from "@/components/LiveWaveform";
import { ConvexSurface } from "@/components/convex-surface";
import { ConvexSheen } from "@/components/convex-sheen";
import { ReferralPrompt } from "@/components/referral/ReferralPrompt";
import { ResultDetail } from "@/components/result/ResultDetail";
import { AssistantChat } from "@/components/chat/AssistantChat";
import { RiskLevel } from "@/lib/types";

const MOCK_SCENARIO_LABEL: Record<RiskLevel, string> = {
  low: "Skenario simulasi A",
  medium: "Skenario simulasi B",
  high: "Skenario simulasi C",
};

const BACKEND_RISK_LABEL: Record<RiskLevel, string> = {
  low: "Risiko rendah",
  medium: "Risiko sedang",
  high: "Risiko tinggi",
};

const AUDIO_TRANSMISSION_DISCLOSURE =
  "Audio dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.";

function formatDuration(seconds: number) {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function ConfidenceBar({ value, label }: { value: number; label: string }) {
  const percentage = Math.round(value * 100);
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between font-mono text-xs text-muted-foreground mb-1">
        <span>{label}</span>
        <span>{percentage}%</span>
      </div>
      <div className="h-1.5 w-full bg-rule rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export function AudioRecorder() {
  const { status, blob, error: recorderError, duration, analyser, start, stop, reset: resetRecorder } =
    useAudioRecorder();
  const { status: analysisStatus, result, error: analysisError, analyze, reset: resetAnalysis } =
    useAnalysis();
  const router = useRouter();
  const flow = useResultFlow();

  const [source, setSource] = useState<{ blob: Blob; name: string } | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isRecording = status === "recording";
  const isProcessing =
    analysisStatus === "uploading" || analysisStatus === "analyzing";

  const activeBlob = source?.blob ?? blob;
  const activeName = source?.name ?? "rekaman.webm";

  const isMockResult = result?.source === "mock";
  const analyzeLabel =
    analysisStatus === "error" ? "Coba kirim lagi" : "Kirim untuk analisis";
  const scenarioLabel = result
    ? isMockResult
      ? MOCK_SCENARIO_LABEL[result.risk]
      : BACKEND_RISK_LABEL[result.risk]
    : "";

  const statusLabel = isRecording
    ? "Sedang merekam"
    : isProcessing
      ? "Sedang menganalisis"
      : activeBlob
        ? "Audio siap"
        : "Siap merekam";

  const handleStop = () => {
    stop();
  };

  const handleRecordReady = () => {
    if (blob) {
      setSource({ blob, name: "rekaman.webm" });
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      resetRecorder();
      resetAnalysis();
      setSource({ blob: file, name: file.name });
    }
  };

  const handleAnalyze = async () => {
    if (!activeBlob) return;

    const data = await analyze(activeBlob, activeName);
    if (data?.risk === "high") flow.openPrompt();
    else if (data) flow.showDetail();
  };

  const handleReset = () => {
    flow.close();
    resetRecorder();
    resetAnalysis();
    setSource(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
      <section className="relative px-6 md:px-10 py-16 md:py-24" aria-label="Alat analisis suara">
        <div className="mx-auto max-w-3xl">
          <header className="mb-10 md:mb-14">
            <h1 className="font-heading text-3xl md:text-4xl lg:text-5xl leading-[1.05] mb-4">
              Deteksi dari suara.
            </h1>
            <p className="text-lg md:text-xl text-ink-2 leading-relaxed max-w-[55ch]">
              Rekam batuk atau pernapasan, lalu kirim ke model. Proyek ini masih
              prototipe; hasil bukan diagnosis medis.
            </p>
          </header>

          <ConvexSheen>
            <ConvexSurface
              className="recorder-workbench"
              variant="panel"
              aria-describedby={recorderError || analysisError ? "recorder-error" : undefined}
            >
              <header className="recorder-workbench__status" aria-live="polite">
                <p className="section-tag">{statusLabel}</p>
                {isRecording ? (
                  <p className="recorder-workbench__timer">{formatDuration(duration)}</p>
                ) : null}
              </header>

              <LiveWaveform analyser={analyser} isActive={isRecording} />

              {(recorderError || analysisError) && (
                <p id="recorder-error" role="alert" className="recorder-workbench__error">
                  {recorderError || analysisError}
                </p>
              )}

              <div className="mt-8 flex flex-col sm:flex-row items-start sm:items-center gap-4">
                {!isRecording && !isProcessing && !result && (
                  <button
                    type="button"
                    onClick={start}
                    disabled={status === "requesting"}
                    className="btn-outline whitespace-nowrap"
                  >
                    {status === "requesting" ? "Meminta izin…" : "Mulai rekam"}
                  </button>
                )}

                {isRecording && (
                  <button
                    type="button"
                    onClick={handleStop}
                    className="btn-outline whitespace-nowrap border-accent text-accent hover:bg-accent hover:text-paper"
                  >
                    Berhenti
                  </button>
                )}

                {!isRecording && !isProcessing && !result && (
                  <>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="audio/*"
                      onChange={handleFileChange}
                      className="sr-only"
                      id="audio-upload"
                    />
                    <label
                      htmlFor="audio-upload"
                      className="cta-link cursor-pointer whitespace-nowrap"
                    >
                      atau unggah file
                    </label>
                  </>
                )}

                {status === "stopped" && !source && (
                  <button
                    type="button"
                    onClick={handleRecordReady}
                    className="cta-link whitespace-nowrap"
                  >
                    Gunakan rekaman ini
                  </button>
                )}
              </div>

              {activeBlob && !result && !isProcessing && (
                <div className="mt-8 pt-6 border-t border-rule">
                  <p className="text-sm text-ink-2 mb-4">
                    File siap: <span className="font-mono text-ink">{activeName}</span>
                  </p>
                  <p className="recorder-workbench__disclosure">
                    {AUDIO_TRANSMISSION_DISCLOSURE}
                  </p>
                  <div className="flex flex-col sm:flex-row items-start gap-4">
                    <button
                      type="button"
                      onClick={handleAnalyze}
                      className="btn-outline whitespace-nowrap"
                    >
                      {analyzeLabel}
                    </button>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="cta-link whitespace-nowrap"
                    >
                      Ulangi
                    </button>
                  </div>
                </div>
              )}

              {isProcessing && (
                <div className="mt-8 pt-6 border-t border-rule">
                  <p role="status" aria-live="polite" className="recorder-workbench__processing">
                    Mengirim audio dan menunggu respons…
                  </p>
                </div>
              )}

              {result && (
                <div className="recorder-workbench__result">
                  {isMockResult ? (
                    <>
                      <div className="recorder-result__badges">
                        <span className="recorder-result__scenario">
                          {MOCK_SCENARIO_LABEL[result.risk]}
                        </span>
                        <span className="recorder-result__mode">Mode demo</span>
                      </div>
                      <p className="recorder-result__sim-copy">
                        Simulasi antarmuka — audio tidak dianalisis.
                      </p>
                      <ConfidenceBar value={result.confidence} label="Nilai simulasi" />
                    </>
                  ) : (
                    <>
                      <div className="recorder-result__badges">
                        <span className="recorder-result__scenario">
                          {BACKEND_RISK_LABEL[result.risk]}
                        </span>
                      </div>
                      <h2 className="recorder-result__title font-heading">
                        {BACKEND_RISK_LABEL[result.risk]}
                      </h2>
                      <p className="recorder-result__message">{result.message}</p>
                      <ConfidenceBar value={result.confidence} label="Skor model" />
                      <p className="recorder-result__recommendation">
                        <span className="recorder-result__label">Rekomendasi</span>
                        {result.recommendation}
                      </p>
                    </>
                  )}
                  <div className="recorder-result__actions">
                    <button
                      type="button"
                      onClick={result.risk === "high" ? flow.openPrompt : flow.showDetail}
                      className="btn-primary whitespace-nowrap"
                    >
                      {result.risk === "high" ? "Tinjau rujukan" : "Detail hasil"}
                    </button>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="btn-outline whitespace-nowrap"
                    >
                      Mulai ulang
                    </button>
                  </div>
                </div>
              )}

              <p className="source-note mt-8">
                *Hasil dari model masih berupa skrining awal. Untuk diagnosis
                pasti, konsultasikan ke dokter atau fasilitas kesehatan.
              </p>
            </ConvexSurface>
          </ConvexSheen>
        </div>

        <ReferralPrompt
          open={flow.stage === "prompt"}
          scenarioLabel={scenarioLabel}
          onClose={flow.close}
          onRefer={() => router.push(`/masuk?next=${encodeURIComponent("/rujukan")}`)}
          onDetail={flow.showDetail}
        />
        <ResultDetail
          open={flow.stage === "detail"}
          result={result}
          onClose={flow.backToPrompt}
          onAnalyzeAi={flow.showChat}
        />
        <AssistantChat
          open={flow.stage === "chat"}
          result={result}
          onClose={flow.showDetail}
        />
      </section>
  );
}
