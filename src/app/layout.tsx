import type { Metadata } from "next";
import {
  Instrument_Serif,
  JetBrains_Mono,
  Plus_Jakarta_Sans,
} from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";

// Instrument Serif hanya punya satu bobot (400, reguler dan miring). Semua aturan
// display di globals.css karena itu dikunci di weight 400 — nilai yang lebih tebal
// akan disintesis browser dan tampak buram.
const instrumentSerif = Instrument_Serif({
  variable: "--font-display",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  display: "swap",
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
    default: "SuaraNafas — Uji model audio riset TB",
    template: "%s · SuaraNafas",
  },
  description:
    "Prototipe untuk menguji model audio TB dari rekaman batuk. Model kandidat belum divalidasi eksternal dan hasilnya bukan diagnosis atau alat keputusan medis.",
  openGraph: {
    title: "SuaraNafas — Uji model audio riset TB",
    description:
      "Uji rekaman batuk dengan model CNN kandidat yang dilatih pada TBscreen. Hanya untuk pengujian prototipe, bukan keputusan medis.",
    locale: "id_ID",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="id"
      // globals.css opts into smooth scrolling; Next needs to be told, or it
      // warns and disables the optimisation on every route change.
      data-scroll-behavior="smooth"
      className={`${instrumentSerif.variable} ${jakarta.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
