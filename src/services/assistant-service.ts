import { AnalysisResult } from "@/lib/types";
import { ChatMessage } from "@/models/chat";

export interface AssistantProvider {
  greeting(result: AnalysisResult | null): string;
  quickReplies(): string[];
  reply(
    input: string,
    result: AnalysisResult | null,
    history: ChatMessage[],
  ): Promise<string>;
}

interface ChatApiResponse {
  message?: string;
  error?: string;
}

const SAFE_ERROR_REPLY =
  "Asisten AI sedang tidak tersedia. Hasil prototipe ini bukan diagnosis; konsultasikan gejala atau kekhawatiran kesehatan kepada tenaga medis.";

function greeting(result: AnalysisResult | null): string {
  if (result?.source === "mock") {
    return "Halo. Hasil saat ini adalah simulasi antarmuka dan audio tidak dianalisis model. Saya tetap dapat menjelaskan alur prototipe dan langkah pemeriksaan TB yang umum.";
  }
  if (result?.source === "backend") {
    return "Halo. Saya dapat membantu menjelaskan hasil skrining dari backend CNN, keterbatasannya, dan langkah tindak lanjut. Hasil ini bukan diagnosis medis.";
  }
  return "Halo. Saya dapat menjelaskan cara kerja prototipe skrining suara dan langkah tindak lanjut kesehatan secara umum.";
}

export function createAssistantProvider(): AssistantProvider {
  return {
    greeting,
    quickReplies() {
      return [
        "Apa arti hasil ini?",
        "Apa langkah selanjutnya?",
        "Apakah ini diagnosis?",
        "Kapan harus ke dokter?",
      ];
    },
    async reply(input, result, history) {
      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            result,
            messages: [
              ...history.map(({ role, content }) => ({ role, content })),
              { role: "user", content: input },
            ],
          }),
        });
        const data = (await response.json()) as ChatApiResponse;
        if (!response.ok || !data.message) return data.error ?? SAFE_ERROR_REPLY;
        return data.message;
      } catch {
        return SAFE_ERROR_REPLY;
      }
    },
  };
}
