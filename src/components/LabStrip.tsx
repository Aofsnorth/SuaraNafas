const ITEMS = [
  {
    title: "Gratis & tanpa akun",
    detail: "Cukup browser dan mikrofon — mulai kapan saja.",
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
  },
  {
    title: "Data dari WHO",
    detail: "Statistik TB bersumber dari Global TB Report 2024.",
    icon: (
      <>
        <path d="M4 19V6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v13" />
        <path d="M4 19h16M8 9h8M8 13h5" />
      </>
    ),
  },
  {
    title: "Terbuka soal batas",
    detail: "Status prototipe & alur data dijelaskan apa adanya.",
    icon: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8h.01M11 12h1v4h1" />
      </>
    ),
  },
  {
    title: "Lanjut ke rujukan",
    detail: "Hasil mengarahkan langkah berikutnya, termasuk ke dokter.",
    icon: (
      <>
        <path d="M4 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
  },
] as const;

export function LabStrip() {
  return (
    <section className="trustbar" aria-label="Jaminan kepercayaan">
      <div className="section-shell">
        <div className="trustbar__row">
          {ITEMS.map((item) => (
            <div className="trust-item" key={item.title}>
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                {item.icon}
              </svg>
              <div>
                <strong>{item.title}</strong>
                <span>{item.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
