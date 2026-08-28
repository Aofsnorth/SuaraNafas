import { Metadata } from "next";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { AnalyzeClient } from "@/components/analyze-client";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Mulai skrining suara",
  description:
    "Rekam atau unggah suara batuk / napas untuk skrining awal tuberkulosis. Gratis, tanpa akun, hasil dalam hitungan detik.",
};

export default function AnalyzePage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="app" />
      <Navbar />
      <main id="konten-utama" className="app-main px-4 sm:px-6 md:px-10">
        <AnalyzeClient />
      </main>
      <Footer />
    </div>
  );
}
