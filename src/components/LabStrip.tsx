const items = [
  { label: "Status", value: "Prototipe hackathon" },
  { label: "Batas", value: "Bukan diagnosis medis" },
  { label: "Data", value: "WHO · tahun + definisi" },
  { label: "Backend", value: "Mode demo jika belum terhubung" },
] as const;

export function LabStrip() {
  return (
    <section className="lab-strip" aria-label="Status prototipe">
      <div className="section-shell lab-strip__row">
        {items.map((item) => (
          <div className="lab-strip-cell" key={item.label}>
            <p className="lab-strip-label">{item.label}</p>
            <p className="lab-strip-value">{item.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
