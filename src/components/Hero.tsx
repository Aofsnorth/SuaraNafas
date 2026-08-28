import Link from "next/link";

export function Hero() {
  return (
    <section className="hero" aria-labelledby="landing-title">
      <div className="section-shell hero__inner">
        <div className="hero__copy">
          <p className="eyebrow">Skrining dini tuberkulosis</p>
          <h1 id="landing-title" className="hero__title">
            Batuk Anda punya pola.{" "}
            <span className="headline-mark">Kami bantu membacanya.</span>
          </h1>
          <p className="hero__lede">
            Rekam suara batuk atau napas langsung dari browser. Model kami
            menganalisis polanya dan memberi indikasi awal — supaya Anda tahu
            kapan waktunya bertemu dokter.
          </p>
          <div className="hero__actions">
            <Link className="btn-primary" href="/analyze">
              Mulai skrining
            </Link>
            <Link className="cta-link" href="#cara-kerja">
              Lihat cara kerjanya
            </Link>
          </div>
          <ul className="hero__micro">
            <li>Gratis, tanpa akun</li>
            <li>Hanya ±2 menit</li>
            <li>Bukan pengganti diagnosis dokter</li>
          </ul>
        </div>

        <div className="hero__visual" aria-hidden="true">
          <div className="breath-visual">
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-ring" />
            <span className="breath-core">napas</span>
            <span className="breath-caption">satu siklus = satu tarikan napas</span>
          </div>
        </div>
      </div>
    </section>
  );
}
