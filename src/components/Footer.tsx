import Link from "next/link";
import { TB_DATA } from "@/lib/tb-data";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="section-shell">
        <p className="site-footer__statement">
          Satu sinyal awal bukan diagnosis. Gunakan hasil untuk memahami langkah
          berikutnya, lalu konfirmasi dengan tenaga medis.
        </p>

        <div className="site-footer__colophon">
          <div className="site-footer__group">
            <p className="site-footer__label">Tim</p>
            <p>Aidan Pitra Habibie</p>
            <p>Muhammad Rizal Anditama</p>
          </div>

          <div className="site-footer__group">
            <p className="site-footer__label">Sumber WHO</p>
            {TB_DATA.map((datum) => (
              <a
                key={datum.sourceUrl}
                href={datum.sourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                {datum.sourceTitle}
              </a>
            ))}
          </div>

          <div className="site-footer__group">
            <p className="site-footer__label">Model 3D</p>
            <p>
              Human Reference Atlas 3D Reference Object Library / NIH Visible
              Human Male, CC-BY 4.0.
            </p>
          </div>

          <div className="site-footer__group">
            <p className="site-footer__label">Lainnya</p>
            <Link href="/transparency">Transparansi aset &amp; batas</Link>
            <p>Prototipe hackathon — bukan diagnosis medis.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
