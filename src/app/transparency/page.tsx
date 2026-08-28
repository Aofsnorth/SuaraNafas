import type { Metadata } from "next";
import Link from "next/link";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { TB_DATA } from "@/lib/tb-data";

export const metadata: Metadata = {
  title: "Transparansi",
  description:
    "Status prototipe, alur audio, mode demo, sumber data WHO, lisensi aset, dan batas medis skrining suara TB.",
};

const SECTIONS = [
  {
    heading: "Status prototipe",
    body: [
      "Proyek ini dibangun untuk GarudaHacks 7.0. Pipeline AI/ML masih dikembangkan tim riset, sehingga antarmuka dapat berjalan dalam mode demo — menampilkan simulasi tanpa menganalisis pola medis apa pun.",
    ],
  },
  {
    heading: "Alur audio Anda",
    body: [
      "Browser merekam audio dengan izin Anda, lalu file dikirim ke /api/analyze. Tanpa BACKEND_API_URL, route menghasilkan simulasi deterministik untuk keperluan demonstrasi. Dengan BACKEND_API_URL, file diteruskan ke endpoint /predict milik backend tim.",
      "Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis — karena itu kami menjelaskannya di sini, agar Anda bisa memutuskan sendiri sebelum menggunakan fitur ini.",
    ],
  },
  {
    heading: "Mode demo & backend",
    body: [
      "Dalam mode demo, hasil selalu diberi label dan tidak memuat klaim klinis apa pun. Ketika backend tervalidasi terhubung, keluaran model ditampilkan sebagaimana adanya — tanpa klaim kalibrasi sampai tim mendokumentasikannya secara resmi.",
    ],
  },
] as const;

export default function TransparencyPage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="document" />
      <Navbar />
      <main id="konten-utama" className="app-main">
        <div className="section-shell">
          <article className="doc mx-auto">
            <p className="eyebrow doc__eyebrow">Dokumen</p>
            <h1 className="doc__title">Transparansi</h1>

            <aside className="doc__note">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8h.01M11 12h1v4h1" />
              </svg>
              <p>
                SuaraNafas adalah prototipe hackathon untuk skrining awal berbasis
                suara. Ini bukan alat diagnosis medis. Untuk gejala atau
                kekhawatiran kesehatan, konsultasikan ke tenaga medis profesional.
              </p>
            </aside>

            {SECTIONS.map((section) => (
              <section key={section.heading}>
                <h2>{section.heading}</h2>
                {section.body.map((paragraph) => (
                  <p key={paragraph.slice(0, 32)}>{paragraph}</p>
                ))}
              </section>
            ))}

            <section>
              <h2>Data statistik (WHO)</h2>
              <ul>
                {TB_DATA.map((datum) => (
                  <li key={datum.sourceUrl}>
                    <a href={datum.sourceUrl} target="_blank" rel="noreferrer">
                      {datum.sourceTitle}
                    </a>{" "}
                    — {datum.value} ({datum.year}).
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h2>Aset &amp; lisensi</h2>
              <p>
                Model 3D paru-paru berasal dari Human Reference Atlas 3D Reference
                Object Library / NIH Visible Human Male (CC-BY 4.0). Seluruh
                visual lain dibuat langsung dengan kode — tidak ada aset hasil
                generator yang dipakai di production. Dataset pelatihan model
                berasal dari CODA-TB yang publik.
              </p>
            </section>

            <section>
              <h2>Batas medis</h2>
              <p>
                Satu indikasi awal bukan diagnosis. Hasil skrining tidak
                menggantikan pemeriksaan dokter, tes dahak, tes molekuler, atau
                rontgen dada.
              </p>
            </section>

            <Link href="/" className="cta-link doc__back">
              Kembali ke beranda
            </Link>
          </article>
        </div>
      </main>
      <Footer />
    </div>
  );
}
