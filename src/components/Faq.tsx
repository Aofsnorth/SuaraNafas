const faqs = [
  {
    question: "Ini diagnosis medis?",
    answer:
      "Tidak. Fitur ini adalah prototipe skrining awal dan tidak menggantikan dokter, pemeriksaan dahak, tes molekuler, atau rontgen dada.",
  },
  {
    question: "Ke mana audio dikirim?",
    answer:
      "Audio dikirim ke /api/analyze. Jika backend dikonfigurasi, route tersebut dapat meneruskan file ke backend tim. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.",
  },
  {
    question: "Apa arti mode demo?",
    answer:
      "Mode demo hanya mensimulasikan tampilan hasil berdasarkan ukuran file. Audio tidak dianalisis untuk pola TB.",
  },
  {
    question: "Seberapa akurat?",
    answer:
      "Belum ada angka akurasi klinis yang dapat diklaim. Tim backend perlu menyelesaikan validasi dataset, kalibrasi, dan evaluasi klinis sebelum skor dapat ditafsirkan.",
  },
] as const;

export function Faq() {
  return (
    <section id="faq" className="landing-section scroll-mt-28" aria-labelledby="faq-title">
      <div className="section-shell faq">
        <header className="section-heading">
          <p className="section-tag">Pertanyaan langsung</p>
          <h2 id="faq-title">Yang perlu Anda tahu sebelum mencoba.</h2>
        </header>
        <div className="faq__list">
          {faqs.map((faq) => (
            <details key={faq.question}>
              <summary>{faq.question}</summary>
              <div className="faq-answer">
                <p>{faq.answer}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
