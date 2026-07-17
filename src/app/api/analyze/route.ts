import { NextRequest, NextResponse } from "next/server";
import {
  AnalysisDetail,
  AnalysisResult,
  BiologicalSex,
  RiskLevel,
} from "@/lib/types";

const MOCK_MESSAGE =
  "Simulasi antarmuka. Prediksi risiko tidak berasal dari model CNN.";

const MOCK_RECOMMENDATION =
  "Hubungkan backend tervalidasi untuk memperoleh output model. Untuk kekhawatiran kesehatan, konsultasikan ke tenaga medis.";

interface BackendPrediction {
  tb_risk_probability: number;
  tb_risk_percent: number;
  risk_band: "lower" | "elevated" | "higher";
  accepted_clips: number;
  disclaimer: string;
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
    message: `Model memproses ${data.accepted_clips} klip audio. Hasil ini adalah skrining awal, bukan diagnosis medis.`,
    recommendation:
      risk === "high"
        ? "Pertimbangkan pemeriksaan lanjutan di fasilitas kesehatan."
        : "Pantau gejala dan konsultasikan ke tenaga medis bila keluhan berlanjut.",
    source: "backend",
    detail: {
      scores: [
        { label: "Indikasi TB", value: confidence },
        { label: "Tidak terindikasi", value: Number((1 - confidence).toFixed(4)) },
      ],
      model: {
        name: "SuaraNafas multimodal TB screening",
        version: "1.0.0",
        durationMs: 0,
      },
    },
  };
}

function isBiologicalSex(value: FormDataEntryValue | null): value is BiologicalSex {
  return value === "female" || value === "male";
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const audio = formData.get("audio");
  const sex = formData.get("sex");

  if (!(audio instanceof File) || audio.size === 0) {
    return NextResponse.json({ error: "File audio diperlukan." }, { status: 400 });
  }

  if (!isBiologicalSex(sex)) {
    return NextResponse.json(
      { error: "Pilih jenis kelamin biologis terlebih dahulu." },
      { status: 400 },
    );
  }

  const backendUrl = process.env.BACKEND_API_URL;

  if (backendUrl) {
    const backendForm = new FormData();
    backendForm.append("audio", audio, audio.name);
    backendForm.append("metadata", JSON.stringify({ sex }));

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

      const data = (await backendResponse.json()) as BackendPrediction;
      return NextResponse.json(mapBackendResult(data));
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
