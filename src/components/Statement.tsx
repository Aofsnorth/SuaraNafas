import Link from "next/link";

export function Statement() {
  return (
    <section className="landing-section final-cta" aria-labelledby="final-cta-title">
      <div className="section-shell final-cta__inner">
        <h2 id="final-cta-title" className="final-cta__title">
          Coba skrining suara sekarang.
        </h2>
        <Link href="/analyze" className="btn-primary">
          Mulai deteksi
        </Link>
        <p className="source-note">
          Mode demo aktif jika backend belum terhubung. Bukan diagnosis medis.
        </p>
      </div>
    </section>
  );
}
