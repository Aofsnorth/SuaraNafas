# Pembayaran QRIS (Midtrans)

Dokumen ini menjelaskan cara kerja tagihan di SuaraNafas, batasnya, dan
bagaimana mengujinya. Untuk status model, lihat
[`MODEL_AUDIT_2026-10-03.md`](MODEL_AUDIT_2026-10-03.md).

---

## 1. Posisi penting

Aplikasi **mau menerima uang**, tetapi yang dijual adalah **layanan eksperimental**,
bukan hasil yang divalidasi secara medis.

| Aspek | Status |
| --- | --- |
| Checkout QRIS terimplementasi | Ya (sandbox + production) |
| Model tervalidasi eksternal | **Belum** |
| Validasi untuk peserta Indonesia | **Belum** — mode eksperimental |
| Production Midtrans + legalitas | **Belum** — perlu diisi sendiri |

Harga tetap: **Rp5.000 per analisis**. Harga ini adalah konstanta di
`src/server/billing/domain.ts` (`ANALYSIS_PRICE_IDR`), bukan input dari client.

---

## 2. Alur pembayaran

```mermaid
sequenceDiagram
    participant U as Pengguna
    participant A as /analyze (Next.js)
    participant C as /api/billing/checkout
    participant M as Midtrans
    participant W as /api/billing/webhook

    U->>A: Isi form, rekam/unggah audio
    U->>A: Centang persetujuan lalu bayar
    A->>C: POST + Idempotency-Key + ID token
    C->>M: POST /v2/charge (QRIS)
    M-->>C: transaction_id + QR URL
    C-->>U: QRIS + expiry
    M-->>W: notifikasi settlement (bertanda tangan)
    W->>W: verifikasi SHA-512 + cocokkan order & nominal
    W-->>M: 200 OK
    U->>A: kirim rekaman (Authorization: Bearer + orderId)
    A->>C: konfirmasi kredit masih ada
    A->>M: /predict pada backend model
    A->>C: konsumsi kredit (compare-and-set)
    A-->>U: hasil + label batasan
```

### Kebijakan penting

1. **Kredit hanya terpakai bila hasil benar-benar keluar.** Konsumsi dilakukan
   *setelah* backend mengembalikan skor yang valid, bukan sebelum. Pengguna tidak
   pernah membayar untuk halaman error atau timeout.
2. **Double-tap tidak berarti bayar dua kali.** `Idempotency-Key` membuat
   percobaan checkout yang sama mengembalikan order yang sama.
3. **Kredit milik satu akun.** `orderId` dicocokkan dengan `uid` pemilik; order
   orang lain dilaporkan "tidak ditemukan", bukan "dilarang".
4. **Nominal berasal dari server.** Webhook menolak settlement yang
   `gross_amount`-nya berbeda dari harga yang kita simpan.
5. **Webhook diverifikasi.** `SHA-512(order_id + status_code + gross_amount +
   server_key)` dibandingkan dengan `signature_key` memakai perbandingan
   constant-time.
6. **Webhook yang hilang tidak menghilangkan pembayaran.** Klien melakukan polling
   ke `GET /api/billing/orders/[orderId]`, dan server melakukan rekonsiliasi
   langsung ke Midtrans bila order masih `pending`.

---

## 3. Persetujuan untuk Indonesia

Indonesia **tidak pernah muncul** di dataset pelatihan mana pun yang dipakai
proyek ini (`docs/DATASET_PROTOCOL.md`). Karena itu backend menolak `ID` dengan
`COUNTRY_NOT_VALIDATED`.

Untuk layanan berbayar, penolakan itu diganti oleh **persetujuan eksplisit**:

1. Pengguna mencentang persetujuan **sebelum membayar**.
2. Persetujuan disimpan **di server** pada order
   (`consentedToUnvalidatedCountry`). Ini bukan flag dari client — kalau begitu
   siapa pun bisa mengirimnya kapan saja.
3. `/api/analyze` hanya meneruskan `allow_unvalidated_country=true` ke backend
   bila order milik pengguna yang sama mencatat persetujuan tersebut.
4. Backend hanya menerima literal persis `"true"`, sama seperti gate kandidat di
   `runtime_config.py`.
5. Respons backend menyertakan
   `country_validation_status: "unvalidated_experimental"`, dan UI menampilkan
   label **"Eksperimental · belum tervalidasi untuk negara Anda"**.

Konsentensi ini menutup Indonesia secara spesifik. Negara di luar daftar
tetap ditolak dengan `OUT_OF_DISTRIBUTION`.

> Catatan jujur: menyetujui layanan eksperimental tetap **bukan** persetujuan
> medis. Partner klinis di Indonesia belum ada (lihat jawaban awal).

---

## 4. Konfigurasi

Isi di `.env.local` (frontend/server):

```env
MIDTRANS_SERVER_KEY=...
MIDTRANS_SANDBOX=true
FIREBASE_CLIENT_EMAIL=...
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_PROJECT_ID=...
```

| Variabel | Wajib | Keterangan |
| --- | --- | --- |
| `MIDTRANS_SERVER_KEY` | Ya | Rahasia. Jangan pernah masuk bundle browser. |
| `MIDTRANS_SANDBOX` | Tidak | Default `true` (aman). |
| `FIREBASE_*` | Ya | Server-side auth + penyimpanan order. |

**Tanpa `MIDTRANS_SERVER_KEY`, checkout otomatis nonaktif** dan analisis tetap
gratis. `next.config.ts` sudah mengizinkan host QRIS pada `img-src`.

### Penyimpanan order

| Environment | Adapter | Catatan |
| --- | --- | --- |
| Production | Firestore | Wajib: bisa diakses lintas instance. |
| Non-production | In-memory | Ringan untuk pengembangan. |

Pergantian ini ada di `src/server/billing/container.ts`.

---

## 5. Menguji

```bash
npm test                      # aturan order, signature, kredit
npm run lint
npm run build

cd deploy/model-space
../../.venv-gpu/Scripts/python.exe -m pytest tests -q
```

Pengujian manual dengan sandbox:

1. Jalankan backend kandidat di `DEPLOYMENT_ENV=staging`.
2. Jalankan `npm run dev` dengan `MIDTRANS_SANDBOX=true`.
3. Bayar memakai kartu virtual Midtrans sandbox.
4. Pastikan kredit terpakai **hanya** setelah hasil muncul.

---

## 6. Sebelum mengaktifkan production

Yang **tidak** bisa diselesaikan lewat kode, dan harus dikerjakan manusia:

- [ ] Aktivasi akun Midtrans production + verifikasi bisnis.
- [ ] Kategori usaha, NPWP/NIK, dan rekening penampung yang jelas.
- [ ] Kebijakan refund tertulis dan kontak support yang bisa dihubungi.
- [ ] Firestore: aturan keamanan yang menolak semua tulis dari client.
- [ ] Klausul privasi & Pemrosesan Data Pribadi (UU PDP) — rekaman batuk
      adalah data kesehatan.
- [ ] Tinjau ulang klaim yang ditampilkan kepada pengguna yang membayar.
- [ ] Decide whether continuing to charge for a model that has not been
      externally validated is ethically defensible.

Yang paling penting: **menjual hasil yang belum tervalidasi kepada pengguna yang
membayar tetap berisiko kesehatan dan hukum.** Kode ini membuat mekanisme
tagihan benar; penilaian klinis dan legal tetap milik manusia.