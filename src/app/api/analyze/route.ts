import { NextRequest, NextResponse } from "next/server";
import { AnalysisDetail, AnalysisResult, RiskLevel } from "@/lib/types";

const MOCK_MESSAGE =
  "Simulasi antarmuka. Audio yang dikirim tidak dianalisis untuk pola TB.";

const MOCK_RECOMMENDATION =
  "Hubungkan backend tervalidasi untuk memperoleh output model. Untuk kekhawatiran kesehatan, konsultasikan ke tenaga medis.";

function buildMockDetail(audio: File, risk: RiskLevel): AnalysisDetail {
  const seed = audio.size;
  const clamp = (n: number) => Number(Math.min(0.98, Math.max(0.02, n)).toFixed(2));
  const highish = risk === "high" ? 0.72 : risk === "medium" ? 0.48 : 0.22;

  const scores = [
    { label: "Skenario simulasi C", value: clamp(highish + (seed % 9) / 100) },
    { label: "Skenario simulasi B", value: clamp(0.5 - (seed % 7) / 100) },
    { label: "Skenario simulasi A", value: clamp(0.3 - (seed % 5) / 100) },
  ];

  const rows = 12;
  const cols = 16;
  const spectrogram: number[][] = Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) =>
      Number(Math.abs(Math.sin((r + 1) * 0.6 + (c + 1) * 0.35 + seed * 0.001)).toFixed(3)),
    ),
  );

  const features = [
    { label: "Durasi tersimulasi", value: `${2 + (seed % 4)}.${seed % 10} dtk` },
    { label: "Rentang frekuensi", value: "80–4000 Hz" },
    { label: "Jumlah frame", value: `${rows * cols}` },
  ];

  return {
    scores,
    spectrogram,
    features,
    model: { name: "Simulasi UI", version: "demo-0.1", durationMs: 1200 },
  };
}

function buildMockResult(audio: File): AnalysisResult {
  const risks: RiskLevel[] = ["low", "medium", "high"];
  const risk = risks[audio.size % risks.length];
  const confidence = 0.62 + ((audio.size % 30) / 100);

  return {
    risk,
    confidence: Number(confidence.toFixed(2)),
    message: MOCK_MESSAGE,
    recommendation: MOCK_RECOMMENDATION,
    source: "mock",
    detail: buildMockDetail(audio, risk),
  };
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const audio = formData.get("audio");

  if (!(audio instanceof File) || audio.size === 0) {
    return NextResponse.json(
      { error: "File audio diperlukan." },
      { status: 400 },
    );
  }

  const backendUrl = process.env.BACKEND_API_URL;

  if (backendUrl) {
    const backendForm = new FormData();
    backendForm.append("audio", audio, audio.name);

    try {
      const backendResponse = await fetch(`${backendUrl}/predict`, {
        method: "POST",
        body: backendForm,
      });

      if (!backendResponse.ok) {
        const detail = await backendResponse.text().catch(() => "Unknown");
        return NextResponse.json(
          { error: "Backend gagal memproses audio.", detail },
          { status: backendResponse.status },
        );
      }

      const data = (await backendResponse.json()) as Omit<
        AnalysisResult,
        "source"
      >;
      const result: AnalysisResult = { ...data, source: "backend" };
      return NextResponse.json(result);
    } catch {
      return NextResponse.json(
        { error: "Tidak bisa terhubung ke backend CNN." },
        { status: 503 },
      );
    }
  }

  await new Promise((resolve) => setTimeout(resolve, 1200));
  return NextResponse.json(buildMockResult(audio));
}
