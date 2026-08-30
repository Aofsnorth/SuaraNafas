import Link from "next/link";

export function Hero() {
  return (
    <section className="hero" aria-labelledby="landing-title">
      <div className="section-shell hero__inner">
        <div className="hero__copy">
          <p className="eyebrow">Prototipe analisis batuk TB</p>
          <h1 id="landing-title" className="hero__title">
            Uji rekaman batuk dengan{" "}
            <span className="headline-mark">model audio penelitian.</span>
          </h1>
          <p className="hero__lede">
            Unggah atau rekam batuk, lalu lihat skor dari model CNN yang dilatih
            pada dataset TBscreen. Model kandidat belum divalidasi untuk diagnosis.
          </p>
          <div className="hero__actions">
            <Link className="btn-primary" href="/analyze">
              Uji rekaman
            </Link>
            <Link className="cta-link" href="#cara-kerja">
              Lihat cara kerjanya
            </Link>
          </div>
          <ul className="hero__micro">
            <li>Tanpa akun</li>
            <li>Raw audio diproses menjadi log-mel spectrogram</li>
            <li>Hanya untuk uji prototipe</li>
          </ul>
        </div>

        <div className="hero__visual" aria-hidden="true">
          <div className="breath-visual">
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-core">batuk</span>
            <span className="breath-caption">visual ritme rekaman batuk</span>
          </div>
        </div>
      </div>
    </section>
  );
}
