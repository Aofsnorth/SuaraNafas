import type { Metadata } from "next";
import { Fraunces, JetBrains_Mono, Plus_Jakarta_Sans } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  display: "swap",
  axes: ["SOFT", "WONK"],
});

// Plus Jakarta Sans: rancangan desainer Indonesia (Tokotype) — pas untuk produk
// berbahasa Indonesia dan bukan font generik.
const jakarta = Plus_Jakarta_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "SuaraNafas — Deteksi dini TB dari suara batuk",
    template: "%s · SuaraNafas",
  },
  description:
    "Skrining awal tuberkulosis lewat suara batuk atau napas Anda. Rekam langsung dari browser, dapatkan indikasi risiko dalam hitungan detik. Gratis, tanpa akun.",
  openGraph: {
    title: "SuaraNafas — Deteksi dini TB dari suara batuk",
    description:
      "Rekam batuk atau napas Anda, model kami membantu membaca polanya. Bukan diagnosis medis — tapi langkah pertama yang bisa dilakukan dari rumah.",
    locale: "id_ID",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="id"
      className={`${fraunces.variable} ${jakarta.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
