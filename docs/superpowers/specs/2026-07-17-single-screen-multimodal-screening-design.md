# Desain Skrining Multimodal Satu Layar

## Tujuan

Mengubah `/analyze` menjadi satu workbench terpusat tanpa modal bertumpuk. Pengguna mengisi data klinis, merekam lima klip batuk, mengirim semuanya otomatis ke model PyTorch, membaca hasil skrining, mencari tenaga kesehatan, atau meminta penjelasan AI tanpa meninggalkan konteks utama.

Produk tetap prototipe skrining awal, bukan alat diagnosis.

## Keputusan Produk

- Seluruh teks antarmuka memakai Bahasa Indonesia.
- Istilah resmi tetap dipertahankan: `SATUSEHAT`, `AI`, `XAI`, nama resource FHIR, dan nama model.
- Model membutuhkan lima klip batuk dan metadata klinis.
- Negara yang tidak tersedia pada data latih tetap dapat diproses.
- Negara yang tidak didukung tidak dipetakan ke negara lain.
- Untuk negara di luar daftar model, semua fitur one-hot `country_*` bernilai `0`.
- Respons model menandai kondisi tersebut dengan `outOfDistribution: true` dan peringatan keterbatasan.
- Audio tidak disimpan secara permanen oleh aplikasi.
- Audio mentah tidak dikirim ke LLM.
- Seluruh popup hasil, detail, rujukan, dan chat dihapus dari alur `/analyze`.

## Struktur Layar

### Bingkai Workbench

Konten utama berada dalam satu panel glassmorphism terpusat dengan jarak yang jelas dari sisi viewport.

- Lebar maksimum desktop sekitar `72rem`.
- Margin horizontal dan vertikal responsif.
- Permukaan memakai blur Gaussian, border tipis, tint `Dark Clinical Midnight`, dan glow cyan lembut.
- Glass hanya membungkus fungsi skrining. Heading halaman tetap berada pada kanvas terbuka.
- Mobile memakai satu kolom tanpa horizontal scroll.

### Tahap Antarmuka

Workbench memakai state machine tunggal:

1. `consent` — penjelasan privasi, keterbatasan, dan izin mikrofon.
2. `clinical` — formulir metadata klinis wajib.
3. `recording` — perekaman lima klip batuk.
4. `submitting` — unggah dan cold-start backend.
5. `result` — hasil skrining dan tiga tindakan.
6. `referral` — pencarian tenaga kesehatan inline.
7. `explanation` — detail model dan percakapan AI inline.
8. `error` — kesalahan yang dapat dipulihkan tanpa kehilangan data yang valid.

Hanya satu tahap utama aktif. Tidak ada `<dialog>` dalam alur ini.

## Formulir Klinis

Formulir mengumpulkan data yang dibutuhkan kontrak model:

- jenis kelamin;
- usia;
- tinggi badan;
- berat badan;
- durasi batuk yang dilaporkan;
- riwayat TB;
- kategori riwayat TB paru, ekstra paru, atau tidak diketahui;
- batuk berdarah;
- denyut jantung;
- suhu tubuh;
- penurunan berat badan;
- merokok dalam satu minggu terakhir;
- demam;
- keringat malam;
- negara;
- status HIV dengan pilihan `Negatif`, `Positif`, atau `Tidak diketahui`.

Validasi dilakukan di browser untuk umpan balik cepat dan di route Next.js sebagai batas kepercayaan. Nilai numerik memiliki rentang wajar. Pesan error memakai Bahasa Indonesia.

Data klinis tidak ditulis ke log. UI menjelaskan bahwa data dikirim ke backend skrining saat pengguna mengirim rekaman.

## Perekaman Audio

### Alur

- Pengguna memberi persetujuan sebelum browser meminta akses mikrofon.
- Pengguna merekam lima klip batuk terpisah.
- Setiap klip memiliki status: `belum direkam`, `merekam`, `siap`, atau `perlu diulang`.
- Waveform bergerak seperti ombak saat idle, lalu memakai data time-domain mikrofon saat aktif.
- Glow cyan tetap lembut. Tidak ada scan line.
- Pengguna dapat mengulang klip tertentu sebelum klip kelima selesai.
- Setelah klip kelima valid, aplikasi otomatis mengirim lima klip dan metadata.
- Tombol batal tersedia selama perekaman. Pengiriman yang sudah dimulai tidak mengirim ulang tanpa tindakan pengguna setelah error.

### Format

Browser tetap memakai `MediaRecorder`. Backend menerima field multipart `audio` berulang. Jika WebM/Opus gagal didekode, backend harus menghasilkan error yang dapat ditindaklanjuti. Dukungan WAV dapat ditambahkan kemudian jika demo WebM tidak stabil; tidak menambah dependency sebelum kegagalan tersebut terbukti.

## Integrasi Model

### Arsitektur

```text
Browser
  → POST /api/screen
  → TB_INFERENCE_URL/predict
  → FastAPI + PyTorch di integrate-models atau Hugging Face Docker Space
```

Model tidak direkonstruksi dalam TypeScript. Bobot `.pt` hanya dimuat oleh backend Python.

### Persiapan Backend

Backend memerlukan:

- `deployment_config.json`;
- `tb_cough_edge_weights_fp32.pt`;
- `model.py`;
- `preprocessing.py`;
- `app.py`;
- FFmpeg/runtime audio yang kompatibel.

`deployment_config.json` belum tersedia. File tersebut harus dibuat dari statistik dataset asli menggunakan `export_deployment_config.py`. Jika CSV sumber tidak tersedia, konfigurasi tidak boleh diisi dengan angka buatan.

### Negara Tidak Didukung

`preprocessing.py` diubah agar negara di luar `IN`, `MG`, `PH`, `SA`, `TZ`, `UG`, dan `VN` tetap diproses:

- semua fitur `country_*` tetap `0`;
- tidak melempar `PreprocessingError`;
- menyimpan penanda `out_of_distribution = true`;
- response `/predict` mengembalikan `outOfDistribution: true`;
- limitations menambahkan penjelasan bahwa negara pengguna tidak terdapat dalam data latih.

Negara yang didukung tetap memakai one-hot sesuai kode negara.

## Kontrak API Skrining

### Request

`POST /api/screen`

`multipart/form-data`:

- `metadata`: JSON string;
- `audio`: lima file dengan field yang sama.

Route Next.js memvalidasi:

- metadata ada dan JSON valid;
- tepat lima klip untuk alur utama;
- setiap file bertipe audio atau `application/octet-stream`;
- file tidak kosong;
- batas ukuran per klip dan total request;
- `TB_INFERENCE_URL` tersedia.

### Response

```ts
interface ScreeningResult {
  tbRiskProbability: number;
  tbRiskPercent: number;
  riskBand: "lower" | "elevated" | "higher";
  acceptedClips: number;
  thresholds: {
    screening: number;
    balanced: number;
    default: number;
    maxAccuracy: number;
  };
  disclaimer: string;
  limitations: string[];
  outOfDistribution: boolean;
  source: "backend";
}
```

Route memetakan snake_case backend ke camelCase frontend. Respons backend dianggap data eksternal dan divalidasi sebelum dirender.

### Error

Semua error Next.js memakai bentuk konsisten:

```ts
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: string[];
  };
}
```

Kode utama:

- `INVALID_METADATA`;
- `INVALID_AUDIO_COUNT`;
- `INVALID_AUDIO`;
- `MODEL_NOT_CONFIGURED`;
- `MODEL_COLD_START`;
- `MODEL_REJECTED_AUDIO`;
- `MODEL_UNAVAILABLE`.

## Tampilan Hasil

Hasil tampil inline dalam workbench.

- Gunakan istilah `Risiko skrining lebih rendah`, `meningkat`, atau `lebih tinggi`.
- Jangan memakai `positif`, `negatif`, atau `diagnosis`.
- Tampilkan probabilitas sebagai keluaran model, bukan kepastian klinis.
- Tampilkan jumlah klip yang diterima.
- Tampilkan disclaimer dan keterbatasan pada surface yang sama.
- Jika `outOfDistribution`, tampilkan peringatan bahwa negara tidak terdapat dalam data latih dan ketidakpastian lebih tinggi.

### Tiga Tindakan

1. `Cari dokter` — tampil hanya untuk hasil atau gejala yang memerlukan tindak lanjut.
2. `Tutup hasil` — mengembalikan workbench ke keadaan awal setelah konfirmasi ringan; tidak memakai modal.
3. `Analisis lengkap AI` — membuka detail model dan chat AI inline.

## SATUSEHAT Sandbox

Dokumentasi resmi yang ditemukan menyediakan:

- OAuth sandbox;
- resource `Practitioner`;
- resource `PractitionerRole`;
- resource `HealthcareService`;
- endpoint transaksi FHIR sandbox.

API publik untuk reservasi `Appointment`, `Schedule`, atau `Slot` belum terkonfirmasi. Karena itu:

- integrasi tahap pertama mengambil atau memetakan data tenaga kesehatan dan layanan dari SATUSEHAT sandbox;
- tombol memakai label `Cari dokter`, bukan mengklaim reservasi nyata;
- pembuatan reservasi tetap simulasi internal sampai endpoint resmi dan kredensial tersedia;
- UI menampilkan label `Sandbox / simulasi`;
- `CLIENT_ID`, `CLIENT_SECRET`, dan Organization ID hanya berada di server environment;
- respons SATUSEHAT divalidasi sebelum dirender.

Referensi resmi:

- `https://satusehat.kemkes.go.id/platform/docs/id/api-code/access-sandbox/`
- `https://satusehat.kemkes.go.id/platform/docs/id/postman-workshop/endpoint-information/`
- `https://satusehat.kemkes.go.id/platform/docs/id/api-catalogue/onboardings/apis/practitioner/`
- `https://satusehat.kemkes.go.id/platform/docs/id/api-catalogue/integrations/apis/healthcare-service/`

## Analisis Lengkap AI

Chat dan detail model berada di bagian bawah hasil, bukan popup.

Next.js menyediakan `POST /api/chat` dan memanggil provider LLM dari server. Request hanya berisi:

- percakapan teks;
- `ScreeningResult` terstruktur;
- metadata model yang tidak mengandung identitas pribadi.

Audio mentah, nama, kredensial, dan data klinis yang tidak diperlukan tidak dikirim ke LLM.

Kebijakan sistem:

- menjelaskan hasil skrining awal;
- tidak mendiagnosis atau menyingkirkan TB;
- tidak meresepkan obat;
- menyebut ketidakpastian dan keterbatasan;
- menganjurkan pemeriksaan mikrobiologis atau tenaga medis bila sesuai;
- mengarahkan ke layanan darurat untuk batuk darah berat, sesak berat, kebingungan, atau tanda gawat.

Output LLM dirender sebagai teks biasa. Tidak memakai `innerHTML`.

Jika konfigurasi LLM tidak tersedia, UI memakai penjelasan deterministik berbasis hasil terstruktur dan memberi label `Penjelasan otomatis`, bukan mengaku memakai LLM.

## Komponen

Komponen minimal yang disarankan:

- `ScreeningWorkbench` — state machine dan orkestrasi.
- `ConsentStep` — persetujuan dan privasi.
- `ClinicalForm` — metadata dan validasi.
- `CoughRecorder` — lima klip dan waveform.
- `ScreeningProgress` — unggah, cold-start, dan retry.
- `ScreeningResultPanel` — hasil dan tindakan.
- `ReferralPanel` — pencarian tenaga kesehatan inline.
- `ScreeningExplanation` — detail model dan chat inline.

Hook:

- `useCoughRecorder` — mengelola lima klip.
- `useScreening` — request dan status model.
- `useScreeningChat` — percakapan AI.

Komponen modal lama tidak dipakai oleh `/analyze`, tetapi tidak perlu dihapus jika route lain masih menggunakannya.

## Error dan Pemulihan

- Izin mikrofon ditolak: jelaskan cara mengaktifkan izin dan tetap sediakan unggah file.
- Klip hening/ditolak: tandai klip terkait, pertahankan klip valid, minta rekam ulang.
- Backend cold-start: tampilkan status khusus dan batas waktu.
- Backend gagal: data dan klip tetap di memori agar pengguna dapat mencoba lagi.
- LLM gagal: hasil skrining tetap terlihat; tampilkan penjelasan deterministik.
- SATUSEHAT gagal: hasil tetap terlihat; tampilkan kontak fasilitas sebagai fallback simulasi.
- Reset: hentikan semua media track, tutup `AudioContext`, batalkan request aktif, hapus Blob dari memori.

## Keamanan dan Privasi

- Validasi file dan metadata di `/api/screen`.
- Batasi ukuran dan jumlah audio.
- Gunakan timeout pada backend, LLM, dan SATUSEHAT.
- Jangan log audio, payload klinis, token, atau response sensitif.
- Rahasia hanya di environment server tanpa prefix `NEXT_PUBLIC_`.
- Jangan menyimpan audio atau metadata secara default.
- Perlakukan output model, SATUSEHAT, dan LLM sebagai data tidak terpercaya.
- LLM tidak dapat memanggil alat, membuat reservasi, atau melakukan tindakan eksternal.

## Pengujian

### Unit

- encoding negara didukung;
- fallback negara tidak didukung menghasilkan semua `country_* = 0`;
- penanda `outOfDistribution` benar;
- validasi metadata;
- validasi lima audio;
- transisi state workbench;
- pemetaan response backend;
- kebijakan label hasil;
- fallback penjelasan tanpa LLM.

### Integrasi

- `/api/screen` meneruskan lima audio dan metadata;
- error FastAPI dipetakan ke `ApiError`;
- timeout/cold-start dapat dicoba ulang;
- `/api/chat` tidak menerima audio;
- kredensial SATUSEHAT tidak bocor ke browser.

### Backend Python

- `deployment_config.json` tersedia;
- `test_model_load.py` lolos;
- negara Indonesia dan negara tidak dikenal tetap menghasilkan input tensor;
- negara didukung tetap one-hot;
- audio hening ditolak;
- lima klip valid menghasilkan response lengkap.

### Aksesibilitas dan Responsif

- keyboard dapat menyelesaikan seluruh alur;
- status rekaman dan proses memakai `aria-live`;
- focus ring terlihat;
- target sentuh minimal 44 × 44 px;
- tidak ada horizontal scroll pada 320, 375, 414, 768, 1024, dan 1440 px;
- `prefers-reduced-motion` membekukan animasi waveform dan glow.

## Kriteria Penerimaan

- `/analyze` tidak membuka modal.
- Hanya satu workbench glass terpusat.
- Lima klip dapat direkam dan diulang.
- Klip kelima memicu pengiriman otomatis setelah metadata valid.
- Model memproses negara yang didukung dan tidak didukung.
- Negara tidak didukung tidak dipalsukan dan diberi peringatan OOD.
- Hasil menampilkan tiga tindakan inline.
- Pencarian dokter memakai integrasi SATUSEHAT sandbox bila dikonfigurasi; reservasi tetap dilabeli simulasi sampai API resmi tersedia.
- Penjelasan AI tidak menerima audio atau identitas.
- Seluruh UI konsisten dalam Bahasa Indonesia.
- Tidak ada klaim diagnosis medis.
