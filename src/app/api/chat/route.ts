import { NextRequest, NextResponse } from "next/server";
import { AnalysisResult } from "@/lib/types";

const MAX_MESSAGES = 12;
const MAX_MESSAGE_LENGTH = 1_500;

const SYSTEM_PROMPT = `Anda adalah Asisten SuaraNafas, pendamping edukasi kesehatan berbahasa Indonesia untuk prototipe skrining awal tuberkulosis berbasis audio batuk.

ATURAN KESELAMATAN WAJIB:
1. Jangan pernah menyatakan pengguna menderita atau tidak menderita TB. Hasil aplikasi bukan diagnosis.
2. Jangan mengubah skor model menjadi kepastian klinis. Sebut sebagai "skor model" atau "hasil skrining prototipe", bukan probabilitas seseorang mengidap TB.
3. Jika sumber hasil adalah "mock", jelaskan tegas bahwa audio tidak dianalisis model dan hasil hanya simulasi antarmuka.
4. Jika sumber hasil adalah "backend", jelaskan bahwa model hanya memproses pola audio dan metadata yang diberikan; hasil tetap memerlukan konfirmasi tenaga medis serta pemeriksaan yang sesuai.
5. Jangan mengarang akurasi, sensitivitas, spesifisitas, kalibrasi, privasi, penghapusan audio, atau kemampuan model yang tidak tersedia pada konteks.
6. Jangan memberikan resep, dosis obat, instruksi menghentikan obat, atau menggantikan evaluasi dokter.
7. Untuk gejala gawat seperti sesak berat, batuk darah banyak, nyeri dada berat, kebingungan, pingsan, atau kondisi memburuk cepat, arahkan mencari pertolongan medis segera.
8. Untuk dugaan TB atau gejala menetap seperti batuk berkepanjangan, demam, keringat malam, atau berat badan turun, sarankan konsultasi ke puskesmas/dokter dan pemeriksaan konfirmasi.
9. Lindungi privasi: jangan meminta nama lengkap, alamat, nomor identitas, rekam medis, atau data sensitif yang tidak diperlukan.
10. Tolak pertanyaan di luar kesehatan, hasil skrining, cara kerja prototipe, dan langkah tindak lanjut secara singkat.

GAYA JAWABAN:
- Gunakan Bahasa Indonesia yang tenang, jelas, dan tidak menghakimi.
- Jawab ringkas, umumnya 2-5 paragraf pendek atau daftar langkah.
- Bedakan fakta dari keterbatasan model.
- Akhiri jawaban yang membahas hasil dengan pengingat bahwa ini bukan diagnosis medis.
- Jangan gunakan bahasa menakutkan atau kepastian palsu.`;

type ChatRole = "user" | "assistant";

interface ChatInputMessage {
  role: ChatRole;
  content: string;
}

interface ChatRequestBody {
  messages?: ChatInputMessage[];
  result?: AnalysisResult | null;
}

interface ProviderResponse {
  choices?: Array<{
    message?: {
      content?: string | Array<{ type?: string; text?: string }>;
    };
  }>;
}

function isChatMessage(value: unknown): value is ChatInputMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<ChatInputMessage>;
  return (
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    message.content.trim().length > 0 &&
    message.content.length <= MAX_MESSAGE_LENGTH
  );
}

function analysisContext(result: AnalysisResult | null | undefined): string {
  if (!result) return "Belum ada hasil analisis pada sesi ini.";

  const sourceDescription =
    result.source === "mock"
      ? "SIMULASI UI: audio tidak dianalisis model."
      : "BACKEND CNN: output skrining prototipe, bukan diagnosis.";

  return [
    sourceDescription,
    `Label internal: ${result.risk}.`,
    `Skor yang ditampilkan: ${Math.round(result.confidence * 100)}%.`,
    `Pesan aplikasi: ${result.message}`,
    `Rekomendasi aplikasi: ${result.recommendation}`,
  ].join("\n");
}

function extractContent(response: ProviderResponse): string | null {
  const content = response.choices?.[0]?.message?.content;
  if (typeof content === "string") return content.trim() || null;
  if (!Array.isArray(content)) return null;

  const text = content
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("\n")
    .trim();
  return text || null;
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.OPENAI_API_KEY;
  const model = process.env.OPENAI_MODEL;
  const baseUrl = (process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, "");

  if (!apiKey || !model) {
    return NextResponse.json(
      { error: "Asisten AI belum dikonfigurasi." },
      { status: 503 },
    );
  }

  let body: ChatRequestBody;
  try {
    body = (await request.json()) as ChatRequestBody;
  } catch {
    return NextResponse.json({ error: "Payload chat tidak valid." }, { status: 400 });
  }

  if (!Array.isArray(body.messages) || body.messages.length === 0) {
    return NextResponse.json({ error: "Pesan chat diperlukan." }, { status: 400 });
  }

  const messages = body.messages.slice(-MAX_MESSAGES);
  if (!messages.every(isChatMessage) || messages.at(-1)?.role !== "user") {
    return NextResponse.json({ error: "Riwayat chat tidak valid." }, { status: 400 });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const providerResponse = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        temperature: 0.2,
        max_tokens: 700,
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          {
            role: "system",
            content: `KONTEKS HASIL SAAT INI:\n${analysisContext(body.result)}`,
          },
          ...messages,
        ],
      }),
      signal: controller.signal,
    });

    if (!providerResponse.ok) {
      return NextResponse.json(
        { error: "Provider AI gagal merespons." },
        { status: 502 },
      );
    }

    const providerBody = (await providerResponse.json()) as ProviderResponse;
    const content = extractContent(providerBody);
    if (!content) {
      return NextResponse.json(
        { error: "Provider AI mengembalikan respons kosong." },
        { status: 502 },
      );
    }

    return NextResponse.json({ message: content });
  } catch (error) {
    const message =
      error instanceof Error && error.name === "AbortError"
        ? "Provider AI melewati batas waktu."
        : "Tidak dapat terhubung ke provider AI.";
    return NextResponse.json({ error: message }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}
