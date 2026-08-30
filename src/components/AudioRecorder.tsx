"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useAnalysis } from "@/hooks/useAnalysis";
import { useResultFlow } from "@/hooks/useResultFlow";
import { LiveWaveform } from "@/components/LiveWaveform";
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

const BACKEND_RISK_LABEL: Record<RiskLevel, string> = {
  low: "Sinyal rujukan lebih rendah — TB tidak tersingkir",
  medium: "Sinyal rujukan meningkat",
  high: "Sinyal rujukan tinggi",
};

const AUDIO_TRANSMISSION_DISCLOSURE =
  "Sebelum dikirim: audio dan data klinis diproses melalui /api/analyze dan dapat diteruskan ke backend analisis. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.";

const COUNTRY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "ID", label: "Indonesia" },
  { value: "KE", label: "Kenya (cohort model kandidat)" },
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
  const secs = seconds % 60 < 10 ? `0${seconds % 60}` : `${seconds % 60}`;
  return `${mins}:${secs}`;
}

function isNumeric(value: string) {
  return value.trim() !== "" && Number.isFinite(Number(value));
}

interface ChoiceOption<T extends string> {
  value: T;
  label: string;
}

interface PillGroupProps<T extends string> {
  legend: string;
  name: string;
  value: T | null;
  options: ReadonlyArray<ChoiceOption<T>>;
  onChange: (value: T) => void;
}

function PillGroup<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
}: PillGroupProps<T>) {
  return (
    <fieldset className="field">
      <legend>{legend}</legend>
      <div className="pill-group__options">
        {options.map((option) => (
          <label key={option.value} className="pill">
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
    <div className="field">
      <label htmlFor={id}>
        {label}
        {optional ? <span className="optional-tag"> · opsional</span> : null}
      </label>
      <div className="field__control">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          className="field-input"
          value={value}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step ?? "any"}
          onChange={(event) => onChange(event.target.value)}
        />
        {suffix ? <span className="field__suffix">{suffix}</span> : null}
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

  // Pemutar ulang: dengarkan dulu sebelum dikirim.
  const playbackUrl = useMemo(
    () => (activeBlob ? URL.createObjectURL(activeBlob) : null),
    [activeBlob],
  );

  useEffect(() => {
    return () => {
      if (playbackUrl) URL.revokeObjectURL(playbackUrl);
    };
  }, [playbackUrl]);

  const isMockResult = result?.source === "mock";
  const isCandidateResult = result?.modelStatus === "candidate";
  const scorePercent = Math.round(
    Math.min(1, Math.max(0, result?.confidence ?? 0)) * 100,
  );

  const statusLabel = isRecording
    ? "Sedang merekam"
    : isProcessing
      ? "Sedang menganalisis"
      : activeBlob
        ? "Rekaman siap"
        : "Belum ada rekaman";

  const submitBlocker = !activeBlob
    ? "Rekam atau unggah audio terlebih dahulu untuk mengaktifkan analisis."
    : !isClinicalCompleteGuard(sex, clinical)
      ? "Lengkapi data klinis di atas untuk mengaktifkan analisis."
      : null;

  const updateClinical = <K extends keyof ClinicalDraft>(
    key: K,
    value: ClinicalDraft[K],
  ) => {
    setClinical((previous) => ({ ...previous, [key]: value }));
  };

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

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      resetRecorder();
      resetAnalysis();
      flow.close();
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
    <section className="relative w-full" aria-label="Alat uji model audio batuk">
      <div
        className={cn(
          "mx-auto w-full transition-all",
          flow.stage !== "idle"
            ? "max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-8 items-start"
            : "max-w-3xl flex flex-col",
        )}
      >
        <div className="w-full">
          <header className="workbench-intro">
            <h1>Uji rekaman batuk Anda.</h1>
            <p>
              Rekam atau unggah suara batuk, isi data pendamping, lalu kirim ke
              model kandidat. Hasilnya hanya untuk menguji prototipe, bukan untuk
              diagnosis atau keputusan medis.
            </p>
          </header>

          <div
            className="panel recorder-workbench"
            aria-describedby={
              recorderError || analysisError || visualizationError
                ? "recorder-error"
                : undefined
            }
          >
            <header
              className="recorder-workbench__status"
              data-state={isRecording ? "recording" : "idle"}
              aria-live="polite"
            >
              <p className="status-label">
                <span className="status-dot" aria-hidden="true" />
                {statusLabel}
              </p>
              {isRecording ? (
                <p className="recorder-workbench__timer">{formatDuration(duration)}</p>
              ) : null}
            </header>

            <div className="recorder-stage">
              <LiveWaveform analyser={analyser} isActive={isRecording} />
            </div>

            {(recorderError || analysisError || visualizationError) && (
              <p id="recorder-error" role="alert" className="recorder-workbench__error">
                {recorderError || analysisError || visualizationError}
              </p>
            )}

            {!result && !isProcessing && (
              <>
                <div className="form-actions mt-4">
                  {!isRecording && (
                    <button
                      type="button"
                      onClick={start}
                      disabled={status === "requesting"}
                      className="btn-primary whitespace-nowrap"
                    >
                      {status === "requesting" ? "Meminta izin…" : "Mulai merekam"}
                    </button>
                  )}

                  {isRecording && (
                    <button
                      type="button"
                      onClick={() => stop()}
                      className="btn-outline whitespace-nowrap"
                    >
                      Berhenti &amp; simpan
                    </button>
                  )}

                  {!isRecording && (
                    <>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="audio/*"
                        onChange={handleFileChange}
                        className="sr-only"
                        id="audio-upload"
                      />
                      <label htmlFor="audio-upload" className="cta-link cursor-pointer">
                        atau unggah rekaman
                      </label>
                    </>
                  )}
                </div>

                {!isRecording && !activeBlob && (
                  <p className="helper-note">
                    Browser akan meminta izin mikrofon saat Anda mulai. Rekam
                    batuk beberapa kali dari jarak ±20 cm agar suaranya jelas.
                  </p>
                )}
              </>
            )}

            {!isRecording && activeBlob && playbackUrl ? (
              <figure className="playback">
                <audio controls src={playbackUrl} preload="metadata" />
                <figcaption>
                  Dengarkan kembali rekaman Anda sebelum mengirim — pastikan
                  suaranya terdengar jelas.
                </figcaption>
              </figure>
            ) : null}

            {!result && !isProcessing && (
              <div className="recorder-workbench__submission">
                <div className="recorder-workbench__file">
                  <span className="text-[0.8rem] font-bold uppercase tracking-[0.08em] text-muted-foreground">Audio</span>
                  <span className="file-name">{activeBlob ? activeName : "Belum dipilih"}</span>
                </div>

                <fieldset className="field">
                  <legend>Jenis kelamin biologis</legend>
                  <div className="pill-group__options">
                    {(["female", "male"] as const).map((option) => (
                      <label key={option} className="pill">
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

                <div className="meta-form">
                  <div>
                    <p className="form-section-title">Data utama</p>
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
                        id="clinical-cough-duration"
                        label="Sudah berapa lama batuk?"
                        suffix="hari"
                        placeholder="cth. 14"
                        min={0}
                        max={3650}
                        value={clinical.coughDurationDays}
                        onChange={(value) => updateClinical("coughDurationDays", value)}
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
                    </div>
                  </div>

                  <div>
                    <p className="form-section-title">Gejala &amp; riwayat</p>
                    <div className="clinical-form__grid">
                      <PillGroup<YesNoAnswer>
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
                        <PillGroup<PriorTbLocation>
                          legend="Lokasi TB sebelumnya"
                          name="tb-prior-location"
                          value={clinical.tbPriorLocation}
                          options={TB_LOCATION_OPTIONS}
                          onChange={(value) => updateClinical("tbPriorLocation", value)}
                        />
                      )}

                      <PillGroup<YesNoAnswer>
                        legend="Demam"
                        name="fever"
                        value={clinical.fever}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => updateClinical("fever", value)}
                      />
                      <PillGroup<YesNoAnswer>
                        legend="Keringat malam"
                        name="night-sweats"
                        value={clinical.nightSweats}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => updateClinical("nightSweats", value)}
                      />
                      <PillGroup<YesNoAnswer>
                        legend="Batuk darah"
                        name="hemoptysis"
                        value={clinical.hemoptysis}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => updateClinical("hemoptysis", value)}
                      />
                      <PillGroup<YesNoAnswer>
                        legend="Penurunan berat badan"
                        name="weight-loss"
                        value={clinical.weightLoss}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => updateClinical("weightLoss", value)}
                      />
                      <PillGroup<YesNoAnswer>
                        legend="Merokok minggu ini"
                        name="smoke-lweek"
                        value={clinical.smokingLastWeek}
                        options={YES_NO_OPTIONS}
                        onChange={(value) => updateClinical("smokingLastWeek", value)}
                      />
                      <PillGroup<HivStatus>
                        legend="Status HIV"
                        name="hiv-status"
                        value={clinical.hivStatus}
                        options={HIV_OPTIONS}
                        onChange={(value) => updateClinical("hivStatus", value)}
                      />
                    </div>
                  </div>

                  <div>
                    <p className="form-section-title">Tambahan (opsional)</p>
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
                      <div className="field">
                        <label htmlFor="clinical-country">Negara</label>
                        <select
                          id="clinical-country"
                          className="field-input"
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
                </div>

                <p className="disclosure">{AUDIO_TRANSMISSION_DISCLOSURE}</p>

                <div>
                  <div className="form-actions">
                    <button
                      type="button"
                      onClick={handleAnalyze}
                      disabled={!activeBlob || !sex || !isClinicalCompleteGuard(sex, clinical)}
                      className="btn-primary"
                    >
                      {analysisStatus === "error"
                        ? "Coba kirim lagi"
                        : "Kirim untuk analisis"}
                    </button>
                    {(activeBlob || sex) && (
                      <button
                        type="button"
                        onClick={handleReset}
                        className="cta-link"
                      >
                        Ulangi dari awal
                      </button>
                    )}
                  </div>
                  {submitBlocker ? (
                    <p className="helper-note mt-2">{submitBlocker}</p>
                  ) : null}
                </div>
              </div>
            )}

            {isProcessing && (
              <p role="status" aria-live="polite" className="recorder-workbench__processing">
                <span className="processing-spinner" aria-hidden="true" />
                Mengirim audio dan menunggu hasil…
              </p>
            )}

            {result && (
              <div
                className="recorder-workbench__result result"
                data-risk={result.risk}
              >
                <div className="result-badges">
                  {isMockResult ? (
                    <>
                      <span className="chip chip--demo">Mode demo — simulasi antarmuka</span>
                      <span className="model-meta">audio tidak dianalisis</span>
                    </>
                  ) : (
                    <span className="chip">
                      {isCandidateResult ? "Kandidat riset · belum tervalidasi" : "Model CNN"}
                    </span>
                  )}
                </div>

                {isMockResult ? (
                  <h2 className="result__title">
                    Ini simulasi, bukan hasil analisis.
                  </h2>
                ) : (
                  <>
                    <h2 className="result__title">
                      {BACKEND_RISK_LABEL[result.risk]}
                    </h2>
                    <p className="result__message">{result.message}</p>
                    <div className="meter">
                      <div className="meter__head">
                        <span>Skor model</span>
                        <span>{scorePercent}%</span>
                      </div>
                      <div
                        className="meter__track"
                        role="meter"
                        aria-label="Skor model"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={scorePercent}
                      >
                        <div
                          className="meter__fill"
                          style={{ width: `${scorePercent}%` }}
                        />
                      </div>
                    </div>
                    <dl className="recommendation">
                      <dt>Langkah yang disarankan</dt>
                      <dd>{result.recommendation}</dd>
                    </dl>
                  </>
                )}

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={result.risk === "high" ? flow.openPrompt : flow.showDetail}
                    className="btn-primary"
                  >
                    {result.risk === "high"
                      ? "Lanjut ke rujukan"
                      : "Lihat detail hasil"}
                  </button>
                  <button type="button" onClick={handleReset} className="btn-outline">
                    Mulai ulang
                  </button>
                </div>

                <p className="source-note">
                  {isCandidateResult
                    ? "Model kandidat ini hanya untuk menguji alur aplikasi. Performa test internal belum memadai dan model belum divalidasi eksternal."
                    : "Hasil model adalah skrining awal, bukan diagnosis. Untuk kepastian, lakukan pemeriksaan lanjutan ke dokter atau fasilitas kesehatan."}
                </p>
              </div>
            )}
          </div>
        </div>

        {flow.stage !== "idle" && (
          <div className="w-full lg:sticky lg:top-28">
            {flow.stage === "prompt" && (
              <ReferralPrompt
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
    </section>
  );
}

function isClinicalCompleteGuard(sex: BiologicalSex | null, clinical: ClinicalDraft) {
  return (
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
    clinical.hivStatus !== null
  );
}
