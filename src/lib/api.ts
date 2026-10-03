import { AnalysisResult, PatientMetadata } from "./types";

/**
 * Backend error codes that need a specific, non-generic explanation in the UI.
 * The backend deliberately distinguishes these, so the client must not collapse
 * them into one "something went wrong" message.
 */
export const ANALYSIS_ERROR_CODES = {
  countryNotValidated: "COUNTRY_NOT_VALIDATED",
  outOfDistribution: "OUT_OF_DISTRIBUTION",
  invalidMetadata: "INVALID_METADATA",
  invalidAudio: "INVALID_AUDIO",
  modelUnavailable: "MODEL_UNAVAILABLE",
} as const;

export type AnalysisErrorCode =
  (typeof ANALYSIS_ERROR_CODES)[keyof typeof ANALYSIS_ERROR_CODES];

const FRIENDLY_MESSAGES: Record<AnalysisErrorCode, string> = {
  [ANALYSIS_ERROR_CODES.countryNotValidated]:
    "Model ini belum pernah divalidasi untuk peserta di Indonesia. Dataset CODA-TB yang dipakai untuk pelatihan tidak memuat peserta dari Indonesia, sehingga hasil analisis tidak dapat dianggap sahih secara medis. Kamu tetap bisa menjelajahi alur analisis, tetapi hasilnya bukan penilaian klinis.",
  [ANALYSIS_ERROR_CODES.outOfDistribution]:
    "Negara peserta berada di luar distribusi data pelatihan model ini, sehingga hasilnya tidak valid.",
  [ANALYSIS_ERROR_CODES.invalidMetadata]:
    "Data klinis yang diisi belum lengkap atau nilainya di luar rentang yang diterima. Periksa kembali formulir.",
  [ANALYSIS_ERROR_CODES.invalidAudio]:
    "Rekaman audio tidak memenuhi persyaratan teknis. Pastikan mikrofon terbuka dan rekaman terdengar jelas.",
  [ANALYSIS_ERROR_CODES.modelUnavailable]:
    "Model belum tersedia di lingkungan ini, sehingga tidak ada prediksi yang dapat dihitung.",
};

export class AnalysisError extends Error {
  readonly code: string | undefined;
  readonly status: number;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "AnalysisError";
    this.status = status;
    this.code = code;
  }

  /** Message safe to show to a non-technical user, preferring our own copy. */
  get userMessage(): string {
    if (this.code && this.code in FRIENDLY_MESSAGES) {
      return FRIENDLY_MESSAGES[this.code as AnalysisErrorCode];
    }
    return this.message || "Gagal menganalisis audio";
  }

  get isOutOfDistribution(): boolean {
    return (
      this.code === ANALYSIS_ERROR_CODES.countryNotValidated ||
      this.code === ANALYSIS_ERROR_CODES.outOfDistribution
    );
  }
}

export async function analyzeAudio(
  blob: Blob,
  metadata: PatientMetadata,
  filename = "recording.webm",
  access: { token: string; orderId: string } | null = null,
): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("audio", blob, filename);
  formData.append("metadata", JSON.stringify(metadata));
  if (access) {
    formData.append("orderId", access.orderId);
  }

  let response: Response;
  try {
    response = await fetch("/api/analyze", {
      method: "POST",
      headers: access ? { Authorization: `Bearer ${access.token}` } : undefined,
      body: formData,
    });
  } catch {
    throw new AnalysisError(
      "Tidak dapat terhubung ke server analisis. Periksa koneksi Anda.",
      0,
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      error?: string;
      code?: string;
    };
    // Preserve the backend code: collapsing every failure into one message
    // hides the difference between "audio rejected" and "your country is not
    // covered by any training data".
    throw new AnalysisError(
      body.error ?? "Gagal menganalisis audio",
      response.status,
      body.code,
    );
  }

  return response.json() as Promise<AnalysisResult>;
}
