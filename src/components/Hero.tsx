import Link from "next/link";
import { BreathingHeadline } from "@/components/breathing-headline";

export function Hero() {
  return (
    <section className="landing-hero" aria-labelledby="landing-title">
      <div className="section-shell landing-hero__inner">
        <p className="section-tag">GarudaHacks 7.0 · prototipe skrining akustik</p>
        <BreathingHeadline id="landing-title">
          Dengarkan paru-paru{" "}
          <span className="headline-mark">berbicara.</span>
        </BreathingHeadline>
        <p className="landing-hero__lede">
          Prototipe skrining awal yang mengubah suara batuk dan pernapasan menjadi
          representasi spektrum untuk antarmuka analisis. Hasil bukan diagnosis medis.
        </p>
        <div className="landing-hero__actions">
          <Link className="btn-primary" href="/analyze">
            Mulai deteksi
          </Link>
          <Link className="cta-link" href="#cara-kerja">
            Lihat cara kerja →
          </Link>
        </div>
      </div>
    </section>
  );
}
