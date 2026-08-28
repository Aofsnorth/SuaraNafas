const STEPS = [
  {
    title: "Rekam suara batuk Anda",
    time: "±30 detik",
    body: "Dari browser, tanpa alat khusus. Bisa juga mengunggah rekaman yang sudah ada.",
  },
  {
    title: "Isi data singkat",
    time: "±1 menit",
    body: "Usia, berat badan, dan gejala seperti demam atau keringat malam membantu model membaca konteksnya.",
  },
  {
    title: "Terima indikasi awal",
    time: "beberapa detik",
    body: "Hasil menunjukkan langkah selanjutnya — termasuk rekomendasi rujukan bila indikasi perlu ditindaklanjuti.",
  },
] as const;

export function Workflow() {
  return (
    <section
      id="cara-kerja"
      className="section section--hairline scroll-mt-24"
      aria-labelledby="workflow-title"
    >
      <div className="section-shell">
        <header className="stats-head">
          <p className="eyebrow">Cara kerja</p>
          <h2 id="workflow-title" className="text-(length:--text-display-lg)">
            Tiga langkah, kurang dari dua menit.
          </h2>
        </header>

        <ol className="steps">
          {STEPS.map((step) => (
            <li className="step" key={step.title}>
              <div className="step__body">
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
              <span className="chip step__time">{step.time}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
