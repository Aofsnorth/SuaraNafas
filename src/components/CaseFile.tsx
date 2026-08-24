import { ConvexSurface } from "@/components/convex-surface";
import { LungModelWrapper } from "@/components/LungModelWrapper";

export function CaseFile() {
  return (
    <section className="landing-section" aria-labelledby="case-file-title">
      <div className="section-shell">
        <ConvexSurface variant="card" className="case-file">
          <div className="case-file__meta">
            <span className="case-file__tag">Spesimen 3D</span>
            <span className="case-file__id">HRA · CC-BY 4.0</span>
          </div>
          <h2 id="case-file-title" className="case-file__name">
            Jelajahi paru-paru yang dibaca model.
          </h2>
          <p className="case-file__body">
            Putar model untuk melihat titik yang menjadi perhatian analisis:
            bronkus, jaringan paru, dan pola frekuensi yang dibandingkan model.
            Visualisasi bersifat edukatif dan bukan hasil pemeriksaan.
          </p>
          <div className="lung-model-shell mt-6 h-[380px] md:h-[460px]">
            <LungModelWrapper />
          </div>
        </ConvexSurface>
      </div>
    </section>
  );
}
