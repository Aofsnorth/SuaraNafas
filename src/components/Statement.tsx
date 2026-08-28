import Link from "next/link";

export function Statement() {
  return (
    <section
      className="section"
      aria-labelledby="final-cta-title"
    >
      <div className="section-shell">
        <div className="final-cta__panel">
          <p className="eyebrow">Siap mencoba?</p>
          <h2 id="final-cta-title" className="final-cta__title">
            Dua menit sekarang bisa memutuskan lebih cepat.
          </h2>
          <div className="final-cta__actions">
            <Link href="/analyze" className="btn-primary">
              Mulai skrining
            </Link>
            <Link href="/transparency" className="cta-link">
              Baca status &amp; batas prototipe
            </Link>
          </div>
          <p className="source-note">
            Gratis · tanpa akun · jika backend belum terhubung, hasil tampil
            sebagai simulasi berlabel &ldquo;Mode demo&rdquo;. Bukan diagnosis medis.
          </p>
        </div>
      </div>
    </section>
  );
}
