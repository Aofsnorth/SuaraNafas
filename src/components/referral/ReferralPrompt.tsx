"use client";

interface ReferralPromptProps {
  onClose: () => void;
  onRefer: () => void;
  onDetail: () => void;
}

export function ReferralPrompt({
  onClose,
  onRefer,
  onDetail,
}: ReferralPromptProps) {
  return (
    <section className="panel referral-prompt" aria-labelledby="referral-prompt-title">
      <div>
        <span className="chip chip--demo mb-4">Mode demo · hasil simulasi</span>
        <h2 id="referral-prompt-title">Langkah yang kami sarankan</h2>
        <p>
          Indikasi pada skenario ini menyarankan pemeriksaan lanjutan. Ini bukan
          diagnosis medis — tapi mempersiapkan rujukan sejak sekarang bisa
          mempercepat langkah Anda.
        </p>
        <p className="mt-3">
          Lihat daftar dokter dan fasilitas kesehatan contoh (data sandbox), atau
          tinjau dulu detail keluaran simulasi.
        </p>
      </div>

      <div className="side-actions">
        <button type="button" className="btn-primary" onClick={onRefer}>
          Lihat rekomendasi dokter
        </button>
        <button type="button" className="cta-link" onClick={onDetail}>
          Detail hasil
        </button>
        <button type="button" className="cta-link" onClick={onClose}>
          Tutup
        </button>
      </div>
    </section>
  );
}
