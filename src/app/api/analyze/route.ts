import { NextRequest, NextResponse } from "next/server";
import {
  AnalysisDetail,
  AnalysisResult,
  HivStatus,
  RiskLevel,
  YesNoAnswer,
} from "@/lib/types";

const MOCK_MESSAGE =
  "Simulasi antarmuka. Prediksi risiko tidak berasal dari model CNN.";

const MOCK_RECOMMENDATION =
  "Hubungkan backend tervalidasi untuk memperoleh output model. Untuk kekhawatiran kesehatan, konsultasikan ke tenaga medis.";

const BACKEND_TIMEOUT_MS = 30_000;

function isDemoModeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" &&
    process.env.ALLOW_DEMO_MODE?.trim().toLowerCase() === "true"
  );
}

interface BackendPrediction {
  tb_risk_probability: number;
  tb_risk_percent: number;
  risk_band: "lower" | "elevated" | "higher";
  accepted_clips: number;
  model_name: string;
  model_version: string;
  model_status: "validated" | "candidate";
  disclaimer: string;
}

function parseBackendPrediction(value: unknown): BackendPrediction {
  if (typeof value !== "object" || value === null) {
    throw new Error("Invalid backend response");
  }
  const payload = value as Record<string, unknown>;
  const probability = payload.tb_risk_probability;
  const percent = payload.tb_risk_percent;
  const acceptedClips = payload.accepted_clips;
  const riskBand = payload.risk_band;
  const modelStatus = payload.model_status;
  if (
    typeof probability !== "number" ||
    !Number.isFinite(probability) ||
    probability < 0 ||
    probability > 1 ||
    typeof percent !== "number" ||
    !Number.isFinite(percent) ||
    percent < 0 ||
    percent > 100 ||
    typeof acceptedClips !== "number" ||
    !Number.isInteger(acceptedClips) ||
    acceptedClips < 1 ||
    acceptedClips > 8 ||
    (riskBand !== "lower" && riskBand !== "elevated" && riskBand !== "higher") ||
    (modelStatus !== "validated" && modelStatus !== "candidate") ||
    typeof payload.model_name !== "string" ||
    payload.model_name.length === 0 ||
    typeof payload.model_version !== "string" ||
    payload.model_version.length === 0 ||
    typeof payload.disclaimer !== "string" ||
    payload.disclaimer.length === 0
  ) {
    throw new Error("Invalid backend response");
  }
  return {
    tb_risk_probability: probability,
    tb_risk_percent: percent,
    risk_band: riskBand,
    accepted_clips: acceptedClips,
    model_name: payload.model_name,
    model_version: payload.model_version,
    model_status: modelStatus,
    disclaimer: payload.disclaimer,
  };
}

function buildMockDetail(audio: File, risk: RiskLevel): AnalysisDetail {
  const seed = audio.size;
  const clamp = (value: number) =>
    Number(Math.min(0.98, Math.max(0.02, value)).toFixed(2));
  const highish = risk === "high" ? 0.72 : risk === "medium" ? 0.48 : 0.22;

  return {
    scores: [
      { label: "Skenario simulasi C", value: clamp(highish + (seed % 9) / 100) },
      { label: "Skenario simulasi B", value: clamp(0.5 - (seed % 7) / 100) },
      { label: "Skenario simulasi A", value: clamp(0.3 - (seed % 5) / 100) },
    ],
    model: { name: "Simulasi UI", version: "demo-0.1", durationMs: 1200 },
  };
}

function buildMockResult(audio: File): AnalysisResult {
  const risks: RiskLevel[] = ["low", "medium", "high"];
  const risk = risks[audio.size % risks.length];
  const confidence = 0.62 + (audio.size % 30) / 100;

  return {
    risk,
    confidence: Number(confidence.toFixed(2)),
    message: MOCK_MESSAGE,
    recommendation: MOCK_RECOMMENDATION,
    source: "mock",
    detail: buildMockDetail(audio, risk),
  };
}

function mapBackendResult(data: BackendPrediction): AnalysisResult {
  const riskMap: Record<BackendPrediction["risk_band"], RiskLevel> = {
    lower: "low",
    elevated: "medium",
    higher: "high",
  };
  const risk = riskMap[data.risk_band];
  const confidence = Math.min(1, Math.max(0, data.tb_risk_probability));

  return {
    risk,
    confidence,
    message:
      data.model_status === "candidate"
        ? `Kandidat riset memproses ${data.accepted_clips} klip. Model belum melalui validasi eksternal dan hasil ini tidak boleh dipakai untuk keputusan medis.`
        : `Model memproses ${data.accepted_clips} klip audio. Hasil ini adalah skrining awal, bukan diagnosis medis.`,
    recommendation:
      data.model_status === "candidate"
        ? "Gunakan hasil ini hanya untuk menguji alur aplikasi. Model kandidat tidak dapat memastikan atau menyingkirkan TB."
        : risk === "high"
          ? "Pertimbangkan pemeriksaan lanjutan di fasilitas kesehatan."
          : "Hasil rendah tidak menyingkirkan TB. Tetap periksa bila ada gejala, paparan, atau kekhawatiran klinis.",
    source: "backend",
    modelStatus: data.model_status,
    detail: {
      scores: [
        { label: "Skor rujukan TB", value: confidence },
        { label: "Komplemen skor model", value: Number((1 - confidence).toFixed(4)) },
      ],
      model: {
        name: data.model_name,
        version: data.model_version,
        durationMs: 0,
      },
    },
  };
}

const MAX_AUDIO_BYTES = 15 * 1024 * 1024;

function isAcceptedAudioType(type: string): boolean {
  return (
    type.startsWith("audio/") ||
    type === "video/webm" ||
    type === "application/octet-stream"
  );
}

interface RawMetadata {
  [key: string]: unknown;
}

type YesNoPayload = "Yes" | "No";
type HivPayload = "Negative" | "Positive" | "Unknown";

interface BackendMetadata {
  sex: "Male" | "Female";
  age: number;
  height: number;
  weight: number;
  reported_cough_dur: number;
  tb_prior: YesNoPayload;
  tb_prior_Pul: YesNoPayload;
  tb_prior_Extrapul: YesNoPayload;
  tb_prior_Unknown: YesNoPayload;
  hemoptysis: YesNoPayload;
  weight_loss: YesNoPayload;
  smoke_lweek: YesNoPayload;
  fever: YesNoPayload;
  night_sweats: YesNoPayload;
  HIVstatus: HivPayload;
  Country: string;
  heart_rate?: number;
  temperature?: number;
}

class MetadataValidationError extends Error {}

function requireNumber(
  payload: RawMetadata,
  field: string,
  min: number,
  max: number,
): number {
  const raw = payload[field];
  if (typeof raw !== "number" || !Number.isFinite(raw)) {
    throw new MetadataValidationError(`Kolom "${field}" wajib berupa angka.`);
  }
  if (raw < min || raw > max) {
    throw new MetadataValidationError(
      `Kolom "${field}" harus di antara ${min} dan ${max}.`,
    );
  }
  return raw;
}

function optionalNumber(
  payload: RawMetadata,
  field: string,
  min: number,
  max: number,
): number | undefined {
  const raw = payload[field];
  if (raw === undefined || raw === null || raw === "") {
    return undefined;
  }
  return requireNumber(payload, field, min, max);
}

function requireYesNo(payload: RawMetadata, field: string): YesNoAnswer {
  const raw = payload[field];
  if (raw !== "yes" && raw !== "no") {
    throw new MetadataValidationError(
      `Kolom "${field}" wajib diisi (yes/no).`,
    );
  }
  return raw;
}

function toYesNo(answer: YesNoAnswer): YesNoPayload {
  return answer === "yes" ? "Yes" : "No";
}

function requireHivStatus(payload: RawMetadata): HivStatus {
  const raw = payload.hivStatus;
  if (raw !== "negative" && raw !== "positive" && raw !== "unknown") {
    throw new MetadataValidationError("Status HIV wajib dipilih.");
  }
  return raw;
}

function requireSex(payload: RawMetadata): "Male" | "Female" {
  const raw = payload.sex;
  if (raw !== "female" && raw !== "male") {
    throw new MetadataValidationError(
      "Pilih jenis kelamin biologis terlebih dahulu.",
    );
  }
  return raw === "male" ? "Male" : "Female";
}

function mapPriorTb(payload: RawMetadata): {
  tb_prior: YesNoPayload;
  tb_prior_Pul: YesNoPayload;
  tb_prior_Extrapul: YesNoPayload;
  tb_prior_Unknown: YesNoPayload;
} {
  const tbPrior = requireYesNo(payload, "tbPrior");
  if (tbPrior === "no") {
    return { tb_prior: "No", tb_prior_Pul: "No", tb_prior_Extrapul: "No", tb_prior_Unknown: "No" };
  }
  const location = payload.tbPriorLocation;
  if (
    location !== "pulmonary" &&
    location !== "extrapulmonary" &&
    location !== "unknown"
  ) {
    throw new MetadataValidationError(
      "Lokasi TB sebelumnya wajib dipilih bila riwayat TB dijawab ya.",
    );
  }
  return {
    tb_prior: "Yes",
    tb_prior_Pul: location === "pulmonary" ? "Yes" : "No",
    tb_prior_Extrapul: location === "extrapulmonary" ? "Yes" : "No",
    tb_prior_Unknown: location === "unknown" ? "Yes" : "No",
  };
}

const COUNTRY_CODE_PATTERN = /^[A-Z]{2}$/;

function sanitizeCountry(payload: RawMetadata): string {
  const raw = typeof payload.country === "string" ? payload.country.trim().toUpperCase() : "";
  if (raw.length > 0 && !COUNTRY_CODE_PATTERN.test(raw)) {
    throw new MetadataValidationError("Kode negara tidak valid.");
  }
  return raw;
}

function sanitizeMetadata(rawMetadata: string | null): BackendMetadata {
  if (!rawMetadata) {
    throw new MetadataValidationError("Data klinis diperlukan.");
  }

  let payload: RawMetadata;
  try {
    payload = JSON.parse(rawMetadata) as RawMetadata;
  } catch {
    throw new MetadataValidationError("Format data klinis tidak valid.");
  }
  if (typeof payload !== "object" || payload === null) {
    throw new MetadataValidationError("Format data klinis tidak valid.");
  }

  const priorTb = mapPriorTb(payload);
  const hivStatus = requireHivStatus(payload);
  const country = sanitizeCountry(payload);

  return {
    sex: requireSex(payload),
    age: requireNumber(payload, "age", 1, 120),
    height: requireNumber(payload, "heightCm", 50, 260),
    weight: requireNumber(payload, "weightKg", 10, 350),
    reported_cough_dur: requireNumber(payload, "coughDurationDays", 0, 3650),
    ...priorTb,
    hemoptysis: toYesNo(requireYesNo(payload, "hemoptysis")),
    weight_loss: toYesNo(requireYesNo(payload, "weightLoss")),
    smoke_lweek: toYesNo(requireYesNo(payload, "smokingLastWeek")),
    fever: toYesNo(requireYesNo(payload, "fever")),
    night_sweats: toYesNo(requireYesNo(payload, "nightSweats")),
    HIVstatus:
      hivStatus === "negative"
        ? "Negative"
        : hivStatus === "positive"
          ? "Positive"
          : "Unknown",
    Country: country,
    heart_rate: optionalNumber(payload, "heartRateBpm", 25, 250),
    temperature: optionalNumber(payload, "temperatureC", 30, 45),
  };
}

export async function POST(request: NextRequest) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Payload audio tidak valid." },
      { status: 400 },
    );
  }

  const audio = formData.get("audio");
  const rawMetadata = formData.get("metadata");

  if (!(audio instanceof File) || audio.size === 0) {
    return NextResponse.json({ error: "File audio diperlukan." }, { status: 400 });
  }

  if (audio.type && !isAcceptedAudioType(audio.type)) {
    return NextResponse.json(
      { error: "Format file harus berupa audio." },
      { status: 415 },
    );
  }

  if (audio.size > MAX_AUDIO_BYTES) {
    return NextResponse.json(
      { error: "Ukuran audio melebihi 15 MB." },
      { status: 413 },
    );
  }

  let metadata: BackendMetadata;
  try {
    metadata = sanitizeMetadata(
      typeof rawMetadata === "string" ? rawMetadata : null,
    );
  } catch (error) {
    const message =
      error instanceof MetadataValidationError
        ? error.message
        : "Data klinis tidak valid.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const backendUrl = process.env.BACKEND_API_URL;

  if (backendUrl) {
    const backendForm = new FormData();
    backendForm.append("audio", audio, audio.name);
    backendForm.append("metadata", JSON.stringify(metadata));

    try {
      const backendResponse = await fetch(`${backendUrl}/predict`, {
        method: "POST",
        body: backendForm,
        signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
      });

      if (!backendResponse.ok) {
        const backendError = await backendResponse
          .json()
          .catch(() => ({ detail: "Kesalahan backend tidak diketahui." }));
        const detail =
          typeof backendError.detail === "string"
            ? backendError.detail
            : "Audio ditolak oleh backend.";
        return NextResponse.json(
          { error: `Backend gagal memproses audio: ${detail}` },
          { status: backendResponse.status },
        );
      }

      try {
        const data = parseBackendPrediction(await backendResponse.json());
        if (process.env.NODE_ENV === "production" && data.model_status !== "validated") {
          return NextResponse.json(
            { error: "Backend belum menyediakan model yang tervalidasi eksternal." },
            { status: 503 },
          );
        }
        return NextResponse.json(mapBackendResult(data));
      } catch {
        return NextResponse.json(
          { error: "Backend mengembalikan respons model yang tidak valid." },
          { status: 502 },
        );
      }
    } catch {
      return NextResponse.json(
        { error: "Backend model tidak dapat dihubungi atau melewati batas waktu." },
        { status: 503 },
      );
    }
  }

  if (isDemoModeEnabled()) {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    return NextResponse.json(buildMockResult(audio));
  }

  return NextResponse.json(
    {
      error:
        "Backend model tervalidasi belum dikonfigurasi. Prediksi simulasi dinonaktifkan demi keselamatan.",
    },
    { status: 503 },
  );
}
