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
import {
  BiologicalSex,
  HivStatus,
  PatientMetadata,
  PriorTbLocation,
  RiskLevel,
  YesNoAnswer,
} from "@/lib/types";
import { extractAudioVisualization } from "@/lib/audio-features";
import { cn } from "@/lib/utils";

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
  "Audio dan data klinis dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.";

const COUNTRY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "ID", label: "Indonesia" },
  { value: "IN", label: "India" },
  { value: "PH", label: "Filipina" },
  { value: "ZA", label: "Afrika Selatan" },
  { value: "UG", label: "Uganda" },
  { value: "VN", label: "Vietnam" },
  { value: "TZ", label: "Tanzania" },
  { value: "MG", label: "Madagaskar" },
];

const HIV_OPTIONS: ReadonlyArray<{ value: HivStatus; label: string }> = [
  { value: "negative", label: "Negatif" },
  { value: "positive", label: "Positif" },
  { value: "unknown", label: "Tidak tahu" },
];

const TB_LOCATION_OPTIONS: ReadonlyArray<{
  value: PriorTbLocation;
  label: string;
}> = [
  { value: "pulmonary", label: "TB paru" },
  { value: "extrapulmonary", label: "Ekstraparu" },
  { value: "unknown", label: "Tidak pasti" },
];

const YES_NO_OPTIONS: ReadonlyArray<{ value: YesNoAnswer; label: string }> = [
  { value: "no", label: "Tidak" },
  { value: "yes", label: "Ya" },
];

interface ClinicalDraft {
  age: string;
  heightCm: string;
  weightKg: string;
  coughDurationDays: string;
  tbPrior: YesNoAnswer | null;
  tbPriorLocation: PriorTbLocation | null;
  fever: YesNoAnswer | null;
  nightSweats: YesNoAnswer | null;
  hemoptysis: YesNoAnswer | null;
  weightLoss: YesNoAnswer | null;
  smokingLastWeek: YesNoAnswer | null;
  hivStatus: HivStatus | null;
  country: string;
  heartRateBpm: string;
  temperatureC: string;
}

const EMPTY_CLINICAL_DRAFT: ClinicalDraft = {
  age: "",
  heightCm: "",
  weightKg: "",
  coughDurationDays: "",
  tbPrior: null,
  tbPriorLocation: null,
  fever: null,
  nightSweats: null,
  hemoptysis: null,
  weightLoss: null,
  smokingLastWeek: null,
  hivStatus: null,
  country: "ID",
  heartRateBpm: "",
  temperatureC: "",
};

function formatDuration(seconds: number) {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function ConfidenceBar({ value, label }: { value: number; label: string }) {
  const percentage = Math.round(Math.min(1, Math.max(0, value)) * 100);
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

function isNumeric(value: string) {
  return value.trim() !== "" && Number.isFinite(Number(value));
}

interface ChoiceOption<T extends string> {
  value: T;
  label: string;
}

interface ChoiceGroupProps<T extends string> {
  legend: string;
  name: string;
  value: T | null;
  options: ReadonlyArray<ChoiceOption<T>>;
  columns?: 2 | 3;
  onChange: (value: T) => void;
}

function ChoiceGroup<T extends string>({
  legend,
  name,
  value,
  options,
  columns = 2,
  onChange,
}: ChoiceGroupProps<T>) {
  return (
    <fieldset className="sex-selector">
      <legend className="section-tag">{legend}</legend>
      <div
        className={cn(
          "sex-selector__options",
          columns === 3 && "clinical-choice-grid--three",
        )}
      >
        {options.map((option) => (
          <label key={option.value} className="sex-selector__option">
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

interface NumericFieldProps {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  optional?: boolean;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  onChange: (value: string) => void;
}

function NumericField({
  id,
  label,
  value,
  placeholder,
  optional = false,
  min,
  max,
  step,
  suffix,
  onChange,
}: NumericFieldProps) {
  return (
    <div className="clinical-field">
      <label className="section-tag" htmlFor={id}>
        {label}
        {optional ? " (opsional)" : ""}
      </label>
      <div className="clinical-field__control">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          className="clinical-input"
          value={value}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step ?? "any"}
          onChange={(event) => onChange(event.target.value)}
        />
        {suffix ? (
          <span className="clinical-field__suffix">{suffix}</span>
        ) : null}
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
  const [sex, setSex] = useState<BiologicalSex | null>(null);
  const [clinical, setClinical] = useState<ClinicalDraft>(EMPTY_CLINICAL_DRAFT);
  const [visualizationError, setVisualizationError] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isRecording = status === "recording";
  const isProcessing =
    isExtracting ||
    analysisStatus === "uploading" ||
    analysisStatus === "analyzing";

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
        : "";

  const updateClinical = <K extends keyof ClinicalDraft>(
    key: K,
    value: ClinicalDraft[K],
  ) => {
    setClinical((previous) => ({ ...previous, [key]: value }));
  };

  const isClinicalComplete =
    sex !== null &&
    isNumeric(clinical.age) &&
    isNumeric(clinical.heightCm) &&
    isNumeric(clinical.weightKg) &&
    isNumeric(clinical.coughDurationDays) &&
    clinical.tbPrior !== null &&
    (clinical.tbPrior === "no" || clinical.tbPriorLocation !== null) &&
    clinical.fever !== null &&
    clinical.nightSweats !== null &&
    clinical.hemoptysis !== null &&
    clinical.weightLoss !== null &&
    clinical.smokingLastWeek !== null &&
    clinical.hivStatus !== null;

  const buildMetadata = (): PatientMetadata => ({
    sex: sex as BiologicalSex,
    age: Number(clinical.age),
    heightCm: Number(clinical.heightCm),
    weightKg: Number(clinical.weightKg),
    coughDurationDays: Number(clinical.coughDurationDays),
    tbPrior: clinical.tbPrior as YesNoAnswer,
    tbPriorLocation:
      clinical.tbPrior === "yes" ? (clinical.tbPriorLocation ?? undefined) : undefined,
    fever: clinical.fever as YesNoAnswer,
    nightSweats: clinical.nightSweats as YesNoAnswer,
    hemoptysis: clinical.hemoptysis as YesNoAnswer,
    weightLoss: clinical.weightLoss as YesNoAnswer,
    smokingLastWeek: clinical.smokingLastWeek as YesNoAnswer,
    hivStatus: clinical.hivStatus as HivStatus,
    country: clinical.country,
    heartRateBpm: isNumeric(clinical.heartRateBpm)
      ? Number(clinical.heartRateBpm)
      : undefined,
    temperatureC: isNumeric(clinical.temperatureC)
      ? Number(clinical.temperatureC)
      : undefined,
  });

  const handleStop = () => {
    stop();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      resetRecorder();
      resetAnalysis();
      setVisualizationError(null);
      setSource({ blob: file, name: file.name });
    }
  };

  const handleAnalyze = async () => {
    if (!activeBlob || !sex || isProcessing) return;

    setVisualizationError(null);
    let visualization;
    setIsExtracting(true);
    try {
      visualization = await extractAudioVisualization(activeBlob);
    } catch (error) {
      setVisualizationError(
        error instanceof Error ? error.message : "Spektrogram audio gagal dibuat.",
      );
      return;
    } finally {
      setIsExtracting(false);
    }

    const data = await analyze(
      visualization.uploadBlob,
      buildMetadata(),
      activeName.replace(/\.[^.]+$/, "") + ".wav",
      {
        spectrogram: visualization.spectrogram,
        spectrogramSource: "audio",
        features: visualization.features,
      },
    );
    if (data?.risk === "high") flow.openPrompt();
    else if (data) flow.showDetail();
  };

  const handleReset = () => {
    flow.close();
    resetRecorder();
    resetAnalysis();
    setSource(null);
    setSex(null);
    setClinical(EMPTY_CLINICAL_DRAFT);
    setVisualizationError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <section className="relative w-full" aria-label="Alat analisis suara">
      <div className={cn("mx-auto w-full transition-all duration-500", flow.stage !== "idle" ? "max-w-5xl" : "max-w-2xl")}>
        <header className="mb-5 md:mb-6">
          <h1 className="font-heading text-3xl md:text-4xl leading-[1.05] mb-2">
            Deteksi dari suara.
          </h1>
          <p className="text-sm md:text-base text-ink-2 leading-relaxed max-w-[62ch]">
            Rekam batuk atau pernapasan, lengkapi data klinis singkat, lalu kirim
            ke model. Proyek ini masih prototipe; hasil bukan diagnosis medis.
          </p>
        </header>

        <div className={cn(
          "w-full transition-all duration-500",
          flow.stage !== "idle" ? "grid grid-cols-1 lg:grid-cols-2 gap-8 items-start" : "flex flex-col"
        )}>
          <div className="w-full">
            <ConvexSheen>
              <ConvexSurface
                className="recorder-workbench"
                variant="panel"
                aria-describedby={
                  recorderError || analysisError || visualizationError
                    ? "recorder-error"
                    : undefined
                }
              >
                <header className="recorder-workbench__status" aria-live="polite">
                  <p className="section-tag">{statusLabel}</p>
                  {isRecording ? (
                    <p className="recorder-workbench__timer">{formatDuration(duration)}</p>
                  ) : null}
                </header>

                <LiveWaveform analyser={analyser} isActive={isRecording} />

                {(recorderError || analysisError || visualizationError) && (
                  <p id="recorder-error" role="alert" className="recorder-workbench__error">
                    {recorderError || analysisError || visualizationError}
                  </p>
                )}

                <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
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
                </div>

                {!result && !isProcessing && (
                  <div className="recorder-workbench__submission">
                    <div className="recorder-workbench__file">
                      <span className="section-tag">Audio</span>
                      <span className="font-mono text-xs text-ink-2 truncate">
                        {activeBlob ? activeName : "Belum dipilih"}
                      </span>
                    </div>

                    <fieldset className="sex-selector">
                      <legend className="section-tag">Jenis kelamin biologis</legend>
                      <div className="sex-selector__options">
                        {(["female", "male"] as const).map((option) => (
                          <label key={option} className="sex-selector__option">
                            <input
                              type="radio"
                              name="sex"
                              value={option}
                              checked={sex === option}
                              onChange={() => setSex(option)}
                            />
                            <span>{option === "female" ? "Perempuan" : "Laki-laki"}</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <div className="clinical-form">
                      <p className="section-tag">Data klinis</p>
                      <div className="clinical-form__grid">
                        <NumericField
                          id="clinical-age"
                          label="Usia"
                          suffix="tahun"
                          placeholder="cth. 32"
                          min={1}
                          max={120}
                          value={clinical.age}
                          onChange={(value) => updateClinical("age", value)}
                        />
                        <NumericField
                          id="clinical-height"
                          label="Tinggi badan"
                          suffix="cm"
                          placeholder="cth. 170"
                          min={50}
                          max={260}
                          value={clinical.heightCm}
                          onChange={(value) => updateClinical("heightCm", value)}
                        />
                        <NumericField
                          id="clinical-weight"
                          label="Berat badan"
                          suffix="kg"
                          placeholder="cth. 58"
                          min={10}
                          max={350}
                          value={clinical.weightKg}
                          onChange={(value) => updateClinical("weightKg", value)}
                        />
                        <NumericField
                          id="clinical-cough-duration"
                          label="Durasi batuk"
                          suffix="hari"
                          placeholder="cth. 14"
                          min={0}
                          max={3650}
                          value={clinical.coughDurationDays}
                          onChange={(value) => updateClinical("coughDurationDays", value)}
                        />
                      </div>

                      <ChoiceGroup<YesNoAnswer>
                        legend="Riwayat TB sebelumnya"
                        name="tb-prior"
                        value={clinical.tbPrior}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => {
                          updateClinical("tbPrior", value);
                          if (value === "no") updateClinical("tbPriorLocation", null);
                        }}
                      />

                      {clinical.tbPrior === "yes" && (
                        <ChoiceGroup<PriorTbLocation>
                          legend="Lokasi TB sebelumnya"
                          name="tb-prior-location"
                          value={clinical.tbPriorLocation}
                          options={TB_LOCATION_OPTIONS}
                          columns={3}
                          onChange={(value) => updateClinical("tbPriorLocation", value)}
                        />
                      )}

                      <div className="clinical-form__grid">
                        <ChoiceGroup<YesNoAnswer>
                          legend="Demam"
                          name="fever"
                          value={clinical.fever}
                          options={YES_NO_OPTIONS}
                          onChange={(value) => updateClinical("fever", value)}
                        />
                        <ChoiceGroup<YesNoAnswer>
                          legend="Keringat malam"
                          name="night-sweats"
                          value={clinical.nightSweats}
                          options={YES_NO_OPTIONS}
                          onChange={(value) => updateClinical("nightSweats", value)}
                        />
                        <ChoiceGroup<YesNoAnswer>
                          legend="Batuk darah"
                          name="hemoptysis"
                          value={clinical.hemoptysis}
                          options={YES_NO_OPTIONS}
                          onChange={(value) => updateClinical("hemoptysis", value)}
                        />
                        <ChoiceGroup<YesNoAnswer>
                          legend="Penurunan berat badan"
                          name="weight-loss"
                          value={clinical.weightLoss}
                          options={YES_NO_OPTIONS}
                          onChange={(value) => updateClinical("weightLoss", value)}
                        />
                        <ChoiceGroup<YesNoAnswer>
                          legend="Merokok minggu ini"
                          name="smoke-lweek"
                          value={clinical.smokingLastWeek}
                          options={YES_NO_OPTIONS}
                          onChange={(value) => updateClinical("smokingLastWeek", value)}
                        />
                        <ChoiceGroup<HivStatus>
                          legend="Status HIV"
                          name="hiv-status"
                          value={clinical.hivStatus}
                          options={HIV_OPTIONS}
                          columns={3}
                          onChange={(value) => updateClinical("hivStatus", value)}
                        />
                      </div>

                      <div className="clinical-form__grid">
                        <NumericField
                          id="clinical-heart-rate"
                          label="Detak jantung"
                          suffix="bpm"
                          placeholder="cth. 88"
                          optional
                          min={25}
                          max={250}
                          value={clinical.heartRateBpm}
                          onChange={(value) => updateClinical("heartRateBpm", value)}
                        />
                        <NumericField
                          id="clinical-temperature"
                          label="Suhu tubuh"
                          suffix="°C"
                          placeholder="cth. 37.1"
                          optional
                          min={30}
                          max={45}
                          step={0.1}
                          value={clinical.temperatureC}
                          onChange={(value) => updateClinical("temperatureC", value)}
                        />
                        <div className="clinical-field">
                          <label className="section-tag" htmlFor="clinical-country">
                            Negara
                          </label>
                          <select
                            id="clinical-country"
                            className="clinical-input"
                            value={clinical.country}
                            onChange={(event) =>
                              updateClinical("country", event.target.value)
                            }
                          >
                            {COUNTRY_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    <p className="recorder-workbench__disclosure">
                      {AUDIO_TRANSMISSION_DISCLOSURE}
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={handleAnalyze}
                        disabled={!activeBlob || !isClinicalComplete}
                        title={
                          !activeBlob || !isClinicalComplete
                            ? "Lengkapi audio dan seluruh isian klinis terlebih dahulu."
                            : undefined
                        }
                        className="btn-outline whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {analyzeLabel}
                      </button>
                      {(activeBlob || sex) && (
                        <button
                          type="button"
                          onClick={handleReset}
                          className="cta-link whitespace-nowrap"
                        >
                          Ulangi
                        </button>
                      )}
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

                <p className="source-note mt-5">
                  *Hasil dari model masih berupa skrining awal. Untuk diagnosis
                  pasti, konsultasikan ke dokter atau fasilitas kesehatan.
                </p>
              </ConvexSurface>
            </ConvexSheen>
          </div>

          {flow.stage !== "idle" && (
            <div className="w-full">
              {flow.stage === "prompt" && (
                <ReferralPrompt
                  scenarioLabel={scenarioLabel}
                  onClose={flow.close}
                  onRefer={() => router.push(`/masuk?next=${encodeURIComponent("/rujukan")}`)}
                  onDetail={flow.showDetail}
                />
              )}
              {flow.stage === "detail" && (
                <ResultDetail
                  result={result}
                  onClose={result?.risk === "high" ? flow.backToPrompt : flow.close}
                  onAnalyzeAi={flow.showChat}
                />
              )}
              {flow.stage === "chat" && (
                <AssistantChat
                  result={result}
                  onClose={flow.showDetail}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
