import Link from "next/link";
import { ConvexSurface } from "@/components/convex-surface";
import { TB_DATA } from "@/lib/tb-data";

export function TbDataSection() {
  return (
    <section id="sains" className="landing-section scroll-mt-28" aria-labelledby="tb-data-title">
      <div className="section-shell">
        <header className="section-heading">
          <p className="section-tag">Data terverifikasi</p>
          <h2 id="tb-data-title">Angka selalu datang bersama konteksnya.</h2>
          <p>
            Estimasi insiden, laporan diagnosis, dan bagian Indonesia mengukur hal
            yang berbeda. Tahun dan definisinya tetap terlihat di setiap kartu.
          </p>
        </header>

        <div className="tb-data-grid">
          {TB_DATA.map((datum, index) => (
            <ConvexSurface
              as="article"
              className={`tb-data-card tb-data-card--${index + 1}`}
              key={datum.label}
              variant="card"
            >
              <p className="tb-data-card__year">WHO · {datum.year}</p>
              <p className="tb-data-card__value">{datum.value}</p>
              <h3>{datum.label}</h3>
              <p>{datum.definition}</p>
              {datum.note ? <p className="tb-data-card__note">{datum.note}</p> : null}
              <Link href={datum.sourceUrl} target="_blank" rel="noreferrer">
                {datum.sourceTitle} ↗
              </Link>
            </ConvexSurface>
          ))}
        </div>
      </div>
    </section>
  );
}
