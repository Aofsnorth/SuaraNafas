const FAQS = [
  {
    question: "Apakah ini diagnosis medis?",
    answer:
      "Bukan. SuaraNafas memberi indikasi awal untuk membantu Anda memutuskan langkah berikutnya. Diagnosis TB hanya bisa ditegakkan lewat pemeriksaan dokter — tes dahak, tes molekuler, atau rontgen dada.",
  },
  {
    question: "Ke mana rekaman suara saya dikirim?",
    answer:
      "Rekaman diproses melalui /api/analyze. Jika backend analisis aktif, file diteruskan ke sana. Status lengkap alur data — termasuk apa yang belum dijamin — kami tulis terbuka di halaman Transparansi.",
  },
  {
    question: "Apa itu mode demo?",
    answer:
      "Mode demo adalah simulasi UI yang hanya dapat diaktifkan secara eksplisit pada development atau staging. Production tidak membuat skor simulasi ketika backend tervalidasi belum tersedia.",
  },
  {
    question: "Seberapa akurat hasilnya?",
    answer:
      "Nested patient-level cross-validation pada 70 subjek menghasilkan pooled AUROC 0,639. Pada operating point sensitif, model masih melewatkan 6 dari 37 subjek TB dan salah merujuk 24 dari 33 subjek non-TB. Model tetap diblokir dari production sampai validasi eksternal lulus.",
  },
  {
    question: "Apakah data saya aman?",
    answer:
      "Kami minta izin mikrofon hanya saat Anda mulai merekam, dan merekam pun dilakukan oleh browser Anda sendiri. Prototipe ini belum melakukan penghapusan otomatis, karena itu kami jelaskan alurnya secara terbuka agar Anda bisa memutuskan sendiri.",
  },
] as const;

export function Faq() {
  return (
    <section
      id="faq"
      className="section section--hairline scroll-mt-24"
      aria-labelledby="faq-title"
    >
      <div className="section-shell">
        <header className="stats-head">
          <p className="eyebrow">Pertanyaan yang wajar</p>
          <h2 id="faq-title" className="text-(length:--text-display-lg)">
            Yang biasanya ditanyakan sebelum mencoba.
          </h2>
        </header>

        <div className="faq-list">
          {FAQS.map((faq) => (
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
