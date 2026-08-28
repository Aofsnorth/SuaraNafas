import Link from "next/link";
import { TB_DATA } from "@/lib/tb-data";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="section-shell">
        <div className="footer-grid">
          <div className="footer-brand">
            <Link
              className="site-nav__wordmark"
              href="/"
              aria-label="Beranda SuaraNafas"
            >
              <span className="wordmark-dot" aria-hidden="true" />
              SuaraNafas
            </Link>
            <p>
              Skrining dini tuberkulosis lewat suara — supaya penundaan pemeriksaan
              berhenti di langkah pertama yang mudah.
            </p>
          </div>

          <div className="footer-col">
            <h3>Jelajahi</h3>
            <ul>
              <li>
                <Link href="/#mengapa-penting">Mengapa penting</Link>
              </li>
              <li>
                <Link href="/#cara-kerja">Cara kerja</Link>
              </li>
              <li>
                <Link href="/#sains">Sains</Link>
              </li>
              <li>
                <Link href="/analyze">Mulai skrining</Link>
              </li>
            </ul>
          </div>

          <div className="footer-col">
            <h3>Transparansi</h3>
            <ul>
              <li>
                <Link href="/transparency">Status &amp; batas prototipe</Link>
              </li>
              <li>
                <p>Statistik TB dari WHO Global TB Report 2024.</p>
              </li>
              <li>
                <p>
                  Model 3D paru: Human Reference Atlas / NIH, CC-BY 4.0.
                </p>
              </li>
            </ul>
          </div>

          <div className="footer-col">
            <h3>Sumber data</h3>
            <ul>
              {TB_DATA.map((datum) => (
                <li key={datum.sourceUrl}>
                  <a href={datum.sourceUrl} target="_blank" rel="noreferrer">
                    {datum.sourceTitle}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="footer-bottom">
          <p>
            Prototipe untuk GarudaHacks 7.0 oleh Aidan Pitra Habibie &amp;
            Muhammad Rizal Anditama. Hasil skrining bukan diagnosis medis —
            konfirmasi selalu ke tenaga kesehatan.
          </p>
          <p>© {new Date().getFullYear()} SuaraNafas</p>
        </div>
      </div>
    </footer>
  );
}
