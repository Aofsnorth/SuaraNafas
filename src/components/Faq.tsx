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
      "Jika backend belum terhubung, situs tetap bisa dicoba dengan hasil simulasi yang selalu diberi label \"Mode demo\". Dalam mode ini audio tidak benar-benar dianalisis.",
  },
  {
    question: "Seberapa akurat hasilnya?",
    answer:
      "Kami belum mengklaim angka akurasi klinis apa pun. Validasi dataset, kalibrasi, dan evaluasi klinis masih dikerjakan tim riset — dan Anda akan selalu melihat batas ini dijelaskan sebelum menggunakan hasilnya.",
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
