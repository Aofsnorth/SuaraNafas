import Link from "next/link";
import { TB_DATA } from "@/lib/tb-data";

export function TbDataSection() {
  return (
    <section
      id="mengapa-penting"
      className="section scroll-mt-24"
      aria-labelledby="tb-data-title"
    >
      <div className="section-shell">
        <header className="stats-head">
          <p className="eyebrow">Mengapa ini penting</p>
          <h2 id="tb-data-title" className="text-(length:--text-display-lg)">
            TB masih ada di sekitar kita — dan sering terlambat ketahuan.
          </h2>
          <p className="lede mt-4">
            Banyak kasus baru ditemukan setelah lama ditunda, karena pemeriksaan
            terasa jauh, mahal, atau menakutkan. Angka-angka berikut menjelaskan
            mengapa skrining awal yang mudah diakses itu penting.
          </p>
        </header>

        <div className="stats-grid">
          {TB_DATA.map((datum) => (
            <article className="stat-card" key={datum.label}>
              <p className="stat-card__year">WHO · {datum.year}</p>
              <p className="stat-card__value">{datum.value}</p>
              <h3>{datum.label}</h3>
              <p>{datum.definition}</p>
              {datum.note ? <p className="stat-card__note">{datum.note}</p> : null}
              <Link href={datum.sourceUrl} target="_blank" rel="noreferrer">
                {datum.sourceTitle}
              </Link>
            </article>
          ))}
        </div>

        <div className="hope-panel">
          <strong>Kabar baiknya: TB bisa dicegah dan disembuhkan.</strong>
          <p>
            Semakin cepat ditemukan, semakin besar peluang kesembuhan — bagi Anda
            maupun orang di sekitar Anda. Skrining suara bukan diagnosis, tapi
            langkah pertama yang bisa dilakukan dari rumah untuk memutus penundaan.
          </p>
        </div>
      </div>
    </section>
  );
}
