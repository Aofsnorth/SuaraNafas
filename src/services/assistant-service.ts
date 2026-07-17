import { AnalysisResult } from "@/lib/types";

export interface AssistantProvider {
  greeting(result: AnalysisResult | null): string;
  quickReplies(): string[];
  reply(input: string, result: AnalysisResult | null): Promise<string>;
}

const DISCLAIMER =
  "Ingat, ini simulasi antarmuka dan bukan diagnosis medis.";

function scenarioLabel(result: AnalysisResult | null): string {
  if (result?.risk === "high") return "Skenario simulasi C";
  if (result?.risk === "medium") return "Skenario simulasi B";
  return "Skenario simulasi A";
}

function scriptedReply(input: string, result: AnalysisResult | null): string {
  const text = input.toLowerCase();

  if (text.includes("diagnos")) {
    return `Bukan. Ini prototipe skrining awal, bukan pengganti dokter, tes dahak, tes molekuler, atau rontgen dada. ${DISCLAIMER}`;
  }
  if (text.includes("langkah") || text.includes("selanjut") || text.includes("lanjut")) {
    return "Langkah yang disarankan: gunakan tombol Rujuk untuk melihat dokter atau fasilitas terdekat, lalu jadwalkan pemeriksaan konfirmasi. Simpan catatan gejala Anda untuk dibawa saat konsultasi.";
  }
  if (text.includes("rujuk") || text.includes("dokter")) {
    return "Untuk membuat rujukan, tekan tombol Rujuk pada layar hasil. Anda akan diminta masuk terlebih dahulu, lalu memilih dokter dari daftar contoh (sandbox).";
  }
  if (text.includes("arti") || text.includes("skenario") || text.includes("hasil")) {
    return `${scenarioLabel(result)} adalah label simulasi untuk memperagakan alur antarmuka. Angkanya adalah nilai simulasi, bukan probabilitas klinis. ${DISCLAIMER}`;
  }
  if (text.includes("akurat") || text.includes("akurasi")) {
    return "Belum ada angka akurasi klinis yang dapat diklaim. Validasi dataset, kalibrasi, dan evaluasi klinis harus diselesaikan lebih dulu.";
  }
  return `Saya dapat menjelaskan skenario simulasi ini, langkah selanjutnya, dan cara membuat rujukan. ${DISCLAIMER}`;
}

export function createAssistantProvider(): AssistantProvider {
  return {
    greeting() {
      return `Halo. Saya asisten simulasi yang membantu menjelaskan hasil ini. ${DISCLAIMER}`;
    },
    quickReplies() {
      return [
        "Apa arti skenario ini?",
        "Apa langkah selanjutnya?",
        "Apakah ini diagnosis?",
        "Bagaimana cara rujukan?",
      ];
    },
    async reply(input, result) {
      await new Promise((resolve) => setTimeout(resolve, 480));
      return scriptedReply(input, result);
    },
  };
}
