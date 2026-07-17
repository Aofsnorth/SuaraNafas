import { AnalysisResult, BiologicalSex } from "./types";

export async function analyzeAudio(
  blob: Blob,
  sex: BiologicalSex,
  filename = "recording.webm",
): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("audio", blob, filename);
  formData.append("sex", sex);

  const response = await fetch("/api/analyze", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error ?? "Gagal menganalisis audio");
  }

  return response.json() as Promise<AnalysisResult>;
}
