import Image from "next/image";

export function Science() {
  return (
    <section className="landing-section" aria-labelledby="science-title">
      <div className="section-shell science-narrative">
        <figure className="science-xai">
          <div className="science-xai__frame">
            <Image
              src="/images/test_xai_output.png"
              alt="Visualisasi keluaran XAI dari eksperimen model audio tuberkulosis"
              width={4470}
              height={2955}
              sizes="(max-width: 768px) calc(100vw - 3rem), 72rem"
              className="science-xai__image"
            />
          </div>
          <figcaption>
            Contoh keluaran XAI dari eksperimen model. Visualisasi ini bukan bukti
            diagnosis klinis.
          </figcaption>
        </figure>

        <div className="science-narrative__copy">
          <h2 id="science-title">Dari suara menuju representasi frekuensi.</h2>
          <p>
            Audio dapat diubah menjadi representasi frekuensi yang dapat dibaca model.
            Pada prototipe ini, bagian tersebut masih menjadi kerangka integrasi dan
            bukan bukti validasi klinis.
          </p>
        </div>
      </div>
    </section>
  );
}
