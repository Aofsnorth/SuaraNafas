import { Metadata } from "next";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { AudioRecorder } from "@/components/AudioRecorder";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "Deteksi Suara — GarudaHacks 7.0",
  description:
    "Rekam atau unggah suara pernapasan / batuk untuk skrining awal tuberkulosis berbasis CNN.",
};

export default function AnalyzePage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="app" />
      <Navbar />
      <main className="relative pt-24 md:pt-36 pb-16 md:pb-24">
        <AudioRecorder />
      </main>
      <Footer />
    </div>
  );
}
