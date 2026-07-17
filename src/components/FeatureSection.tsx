import { GlassCard } from "./GlassCard";

const features = [
  {
    title: "Untuk Semua",
    description:
      "Mudah digunakan untuk membantu akses skrining kesehatan paru-paru.",
  },
  {
    title: "Data Aman",
    description:
      "Pemrosesan data dilakukan dengan pendekatan keamanan modern.",
  },
];

export function FeatureSection() {
  return (
    <section id="cara-kerja" className="relative py-20 px-4">
      <div className="mx-auto max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6">
        {features.map((feature) => (
          <GlassCard key={feature.title}>
            <h3 className="text-2xl font-heading mb-2">{feature.title}</h3>
            <p className="text-muted-foreground leading-relaxed">
              {feature.description}
            </p>
          </GlassCard>
        ))}
      </div>
    </section>
  );
}
