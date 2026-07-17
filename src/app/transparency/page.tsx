import type { Metadata } from "next";
import Link from "next/link";
import { Background } from "@/components/Background";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ConvexSurface } from "@/components/convex-surface";
import { TB_DATA } from "@/lib/tb-data";

export const metadata: Metadata = {
  title: "Transparansi — GarudaHacks 7.0",
  description:
    "Status prototipe, alur audio, mode demo, sumber data WHO, lisensi aset, dan batas medis untuk skrining suara TB.",
};

export default function TransparencyPage() {
  return (
    <div className="relative min-h-screen overflow-x-clip">
      <Background variant="document" />
      <Navbar />
      <main className="relative pt-24 md:pt-36 pb-16 md:pb-24">
        <div className="section-shell">
          <article className="doc">
            <p className="section-tag">Dokumen</p>
            <h1 className="doc__title">Transparansi</h1>

            <ConvexSurface variant="note" className="doc__note">
              <p>
                Fitur ini adalah prototipe hackathon untuk skrining awal berbasis
                suara. Ini bukan alat diagnosis medis. Untuk gejala atau
                kekhawatiran kesehatan, konsultasikan ke tenaga medis profesional.
              </p>
            </ConvexSurface>

            <section>
              <h2>Status prototipe</h2>
              <p>
                Proyek ini dibangun untuk GarudaHacks 7.0. Pipeline AI/ML masih
                dalam pengembangan oleh tim backend, sehingga antarmuka dapat
                berjalan dalam mode demo tanpa menganalisis pola medis apa pun.
              </p>
            </section>

            <section>
              <h2>Alur audio</h2>
              <p>
                Browser mengirim file ke /api/analyze. Tanpa BACKEND_API_URL, route
                mengembalikan simulasi UI deterministik berdasarkan ukuran file.
                Dengan BACKEND_API_URL, route dapat meneruskan file ke endpoint
                /predict milik backend tim. Prototipe ini belum menjamin pemrosesan
                lokal atau penghapusan otomatis.
              </p>
            </section>

            <section>
              <h2>Mode demo dan backend</h2>
              <p>
                Dalam mode demo, hasil ditampilkan sebagai skenario simulasi dan
                tidak memuat label risiko klinis. Ketika backend tervalidasi
                terhubung, output model ditampilkan apa adanya tanpa klaim
                kalibrasi hingga tim mendokumentasikannya.
              </p>
            </section>

            <section>
              <h2>Data WHO</h2>
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
              <h2>Aset dan lisensi</h2>
              <p>
                Model 3D paru-paru berasal dari Human Reference Atlas 3D Reference
                Object Library / NIH Visible Human Male, di bawah lisensi CC-BY 4.0.
                Aset visual lain dibuat langsung dengan kode. Referensi navbar hanya
                dipakai sebagai inspirasi publik dan tidak ikut dipublikasikan.
              </p>
            </section>

            <section>
              <h2>Batas medis</h2>
              <p>
                Satu sinyal awal bukan diagnosis. Hasil skrining tidak menggantikan
                pemeriksaan dokter, tes dahak, tes molekuler, atau rontgen dada.
              </p>
            </section>

            <Link href="/" className="cta-link doc__back">
              Kembali ke beranda →
            </Link>
          </article>
        </div>
      </main>
      <Footer />
    </div>
  );
}
