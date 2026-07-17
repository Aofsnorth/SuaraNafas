import { Metadata } from "next";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { AnalyzeClient } from "@/components/analyze-client";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Deteksi Suara — SuaraNafas",
  description:
    "Rekam atau unggah suara pernapasan / batuk untuk skrining awal tuberkulosis berbasis CNN.",
};

export default function AnalyzePage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="app" />
      <Navbar />
      <main className="relative pt-24 md:pt-36 pb-16 md:pb-24 px-4 sm:px-6 md:px-10">
        <div className="mx-auto max-w-6xl rounded-2xl border border-white/[0.08] bg-white/[0.04] p-4 sm:p-6 md:p-10 backdrop-blur-2xl shadow-[0_8px_64px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.06)]">
          <AnalyzeClient />
        </div>
      </main>
      <Footer />
    </div>
  );
}
