import Image from "next/image";

const POINTS = [
  {
    title: "Membaca pola, bukan menduga-duga",
    body: "Audio diubah menjadi mel-spektrogram — semacam sidik jari frekuensi dari setiap batuk.",
  },
  {
    title: "Dilatih dari data publik",
    body: "Model belajar dari dataset batuk terbuka TBscreen (Zenodo, lisensi CC-BY 4.0) yang dipakai riset TB.",
  },
  {
    title: "Keputusan tetap di tangan manusia",
    body: "Hasil model adalah indikasi awal. Penilaian medis tetap datang dari dokter.",
  },
] as const;

export function Science() {
  return (
    <section
      id="sains"
      className="section section--tint scroll-mt-24"
      aria-labelledby="science-title"
    >
      <div className="section-shell science-grid">
        <figure className="science-figure">
          <div className="science-figure__frame">
            <Image
              src="/images/xai-from-scratch.png"
              alt="Visualisasi keluaran XAI: bagian audio yang paling memengaruhi keputusan model"
              width={1280}
              height={720}
              sizes="(max-width: 960px) calc(100vw - 3rem), 40rem"
              className="science-figure__image"
            />
          </div>
          <figcaption>
            Peta sensitivitas occlusion dari model yang kami latih dari nol:
            area yang paling memengaruhi keputusan model. Visualisasi edukatif,
            bukan bukti diagnosis.
          </figcaption>
        </figure>

        <div className="science-copy">
          <p className="eyebrow">Sains di baliknya</p>
          <h2 id="science-title">
            Seperti telinga yang dilatih mendengar ratusan batuk.
          </h2>
          <p>
            Model CNN kami memperlakukan suara seperti gambar: frekuensi batuk dan
            napas dipetakan, lalu dicocokkan dengan pola yang pernah dipelajari.
          </p>
          <ul className="science-points">
            {POINTS.map((point) => (
              <li key={point.title}>
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="m5 12.5 4.5 4.5L19 7.5" />
                </svg>
                <span>
                  <strong>{point.title}.</strong> {point.body}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
