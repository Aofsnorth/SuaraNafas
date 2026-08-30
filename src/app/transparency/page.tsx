import type { Metadata } from "next";
import Link from "next/link";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { TB_DATA } from "@/lib/tb-data";

export const metadata: Metadata = {
  title: "Transparansi",
  description:
    "Status model audio kandidat, alur pengiriman rekaman batuk, mode demo, sumber data, lisensi aset, dan batas penggunaan.",
};

const SECTIONS = [
  {
    heading: "Status prototipe",
    body: [
      "Proyek ini dibangun untuk GarudaHacks 7.0. Kandidat residual v3 dilatih dari bobot acak pada TBscreen. Nested patient-level cross-validation pada 70 pasien menghasilkan pooled AUROC 0,639. Pada operating point sensitif yang dipilih hanya dari inner validation, model mendeteksi 31 dari 37 pasien TB dan melewatkan 6, serta salah merujuk 24 dari 33 pasien non-TB. Model belum divalidasi eksternal dan belum layak untuk keputusan medis.",
    ],
  },
  {
    heading: "Alur audio Anda",
    body: [
      "Browser merekam audio dengan izin Anda, lalu file dikirim ke /api/analyze. Dengan BACKEND_API_URL, file diteruskan ke endpoint /predict milik backend tim. Tanpa backend, konfigurasi production menolak prediksi dan tidak membuat skor simulasi.",
      "Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis — karena itu kami menjelaskannya di sini, agar Anda bisa memutuskan sendiri sebelum menggunakan fitur ini.",
    ],
  },
  {
    heading: "Mode demo & backend",
    body: [
      "Mode simulasi hanya dapat diaktifkan secara eksplisit di lingkungan non-production. Untuk pengujian lokal atau staging, backend dapat memuat checkpoint kandidat dengan ALLOW_BLOCKED_CANDIDATE=true; hasilnya tetap berlabel kandidat riset. DEPLOYMENT_ENV=production menolak kandidat meskipun flag tersebut ikut terpasang, dan hanya menerima manifest yang lulus validasi eksternal.",
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
                SuaraNafas adalah prototipe hackathon untuk menguji model audio TB
                dari rekaman batuk. Model kandidat belum divalidasi eksternal dan
                bukan alat diagnosis. Untuk gejala atau kekhawatiran kesehatan,
                konsultasikan ke tenaga medis profesional.
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
                visual lain dibuat langsung dengan kode. Dataset pelatihan model
                berasal dari TBscreen (Zenodo 10431329, CC-BY 4.0). Visualisasi
                sensitivitas dibuat dari checkpoint kandidat proyek ini.
              </p>
            </section>

            <section>
              <h2>Batas medis</h2>
              <p>
                Skor model bukan diagnosis dan tidak dapat memastikan atau
                menyingkirkan TB. Hasil ini tidak menggantikan pemeriksaan dokter,
                tes dahak, tes molekuler, atau rontgen dada.
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
