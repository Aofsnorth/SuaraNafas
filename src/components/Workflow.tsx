import { ConvexSurface } from "@/components/convex-surface";

const steps = [
  {
    no: "01",
    kicker: "Rekam",
    title: "Rekam suara",
    body: "Rekam batuk atau pernapasan langsung dari browser. Tidak perlu alat klinis khusus.",
  },
  {
    no: "02",
    kicker: "Bentuk spektrum",
    title: "Bentuk spektrum",
    body: "Audio diubah menjadi representasi frekuensi sebagai alur antarmuka. Pada prototipe ini bagian tersebut masih kerangka integrasi, bukan inferensi diagnostik yang tervalidasi.",
  },
  {
    no: "03",
    kicker: "Pahami hasil",
    title: "Pahami hasil",
    body: "Antarmuka menampilkan skenario dan mengarahkan langkah lanjutan. Hasil bukan diagnosis.",
  },
] as const;

export function Workflow() {
  return (
    <section id="cara-kerja" className="landing-section scroll-mt-28" aria-labelledby="workflow-title">
      <div className="section-shell">
        <header className="section-heading">
          <p className="section-tag">Cara kerja</p>
          <h2 id="workflow-title">Dari suara menuju sinyal yang bisa dibaca.</h2>
          <p>Tiga tahap sederhana. Hasilnya mengarahkan langkah berikutnya, bukan mendiagnosis.</p>
        </header>

        <div className="workflow-grid">
          <div className="workflow-steps">
            {steps.map((step) => (
              <ConvexSurface as="article" variant="card" className="workflow-card" key={step.no}>
                <span className="workflow-card__step">
                  {step.no} · {step.kicker}
                </span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </ConvexSurface>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
