import { LungModelWrapper } from "@/components/LungModelWrapper";

export function CaseFile() {
  return (
    <section className="section" aria-labelledby="case-file-title">
      <div className="section-shell">
        <div className="panel lung-panel">
          <div className="lung-panel__head">
            <div className="lung-panel__meta">
              <span className="chip">Visualisasi edukatif</span>
              <span className="chip">HRA · CC-BY 4.0</span>
            </div>
            <h2 id="case-file-title">Lihat organ yang dibaca model.</h2>
            <p className="lung-panel__lede">
              Putar model paru-paru untuk melihat titik-titik yang menjadi
              perhatian analisis: bronkus, jaringan paru, dan sekitarnya.
              Model ini alat bantu pemahaman — bukan hasil pemeriksaan Anda.
            </p>
          </div>
          <div className="lung-model-shell">
            <LungModelWrapper />
          </div>
        </div>
      </div>
    </section>
  );
}
