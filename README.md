# SuaraNafas — GarudaHacks 7.0

Web app untuk riset skrining tuberkulosis (TB) melalui analisis rekaman suara batuk menggunakan model CNN audio.

## Fitur Utama

- **Rekam / unggah audio** batuk langsung dari browser.
- **Analisis CNN audio** — model from-scratch yang membaca fitur log-mel spectrogram tanpa bobot pretrained.
- **Pembayaran QRIS (opsional)** — satu kredit analisis Rp5.000 lewat Midtrans, dengan verifikasi webhook, idempotensi, dan kredit yang hanya terpakai bila hasil benar-benar keluar.
- **Mode eksperimental Indonesia** — peserta di Indonesia bisa dianalisis setelah persetujuan eksplisit, dengan label "belum tervalidasi untuk negara Anda".
- **Visualisasi 3D** paru-paru interaktif berbasis React Three Fiber.
- **Referral sandbox** bergaya SatuSehat — daftar contoh dokter/faskes untuk simulasi rujukan (data sandbox, bukan faskes nyata).
- **Mode demo terisolasi** — simulasi hanya tersedia melalui opt-in eksplisit di lingkungan non-production.

## Tech Stack

| Layer | Teknologi |
|---|---|
| Framework | Next.js 16 (App Router) |
| Bahasa | TypeScript |
| Styling | Tailwind CSS v4 |
| Komponen UI | Dibuat sendiri di `src/components/` (tanpa pustaka komponen pihak ketiga) |
| 3D | React Three Fiber, Three.js, Drei |
| Animasi | Framer Motion |
| Auth | Firebase Authentication |
| Backend ML | FastAPI + PyTorch (deploy/model-space) |
| Deployment | Vercel (frontend), Hugging Face Spaces / Docker (backend) |

## Setup & Instalasi

```bash
git clone https://github.com/Aofsnorth/SuaraNafas.git
cd SuaraNafas
npm install
npm run dev
```

Aplikasi berjalan di [http://localhost:3000](http://localhost:3000).

### Konfigurasi Environment

Buat file `.env.local` di root untuk menghubungkan backend tervalidasi:

```env
BACKEND_API_URL=https://your-cnn-backend.example.com
ALLOW_DEMO_MODE=false
```

Tanpa backend yang tervalidasi, production mengembalikan HTTP 503 dan tidak
membuat probabilitas simulasi.

## Build untuk Production

```bash
npm run build
npm run start
```

### Build dari network share (UNC)

Build produksi memakai opsi resmi `next build --webpack` karena cache persisten
Turbopack dapat korup pada filesystem removable/network tertentu. Mode development
tetap memakai `next dev`.

Jika project dibuka dari path UNC (`\\...\...`) di Windows, gunakan skrip build
shadow agar proses build dan cache berjalan di disk lokal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Skrip menyalin sumber ke `%LOCALAPPDATA%\SuaraNafas\build-shadow`,
meng-install dependensi bila lockfile berubah, menjalankan `next build`,
dan mencetak lokasi hasil untuk preview `npm run start`.

### Pemeriksaan sebelum commit

```bash
npm run lint       # ESLint
npm run typecheck  # tsc --noEmit
npm test           # vitest run (test/unit)
```

### Troubleshooting console

- **`eval() is not supported`** — hanya muncul di `next dev`. React memakai eval
  untuk menyusun ulang call stack saat development, jadi CSP diberi
  `'unsafe-eval'` hanya ketika `NODE_ENV=development`; production tidak pernah.
- **`Could not load potsdamer_platz_1k.hdr`** — sudah hilang. Environment HDR `preset`
  diunduh dari CDN pihak ketiga dan diblokir `connect-src`. Visualisasi kini
  memakai `Lightformer` drei, jadi environment map dirakit di GPU tanpa jaringan.
- **`scroll-behavior: smooth` warning** — `<html>` sudah diberi
  `data-scroll-behavior="smooth"` di `src/app/layout.tsx`.
- **`THREE.Clock has been deprecated`** — `three` r183+ sudah deprecated
  `THREE.Clock`, tetapi `@react-three/fiber` masih membuatnya di dalam paketnya
  (termasuk di 9.8.1, versi 9.x terbaru), jadi tidak ada call site di aplikasi
  ini yang bisa diubah. Pesan itu kosmetik, muncul sekali per sesi, dan hanya
  di development; `src/lib/three-deprecations.ts` menyaring tepat satu string
  itu. Hapus filter tersebut begitu R3F beralih ke `THREE.Timer`.

## Backend ML (`deploy/model-space`)

Backend FastAPI default menolak checkpoint yang belum lolos validasi eksternal dan
melaporkan `model_status: unavailable`. Untuk menguji integrasi penuh dengan
kandidat CODA fusion v3 yang sudah ada di repo — tanpa training ulang:

```bash
cd deploy/model-space
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
DEPLOYMENT_ENV=staging \
MODEL_MANIFEST_PATH=../../coda-tb/output-v3/manifest-fusion.json \
ALLOW_BLOCKED_CANDIDATE=true \
uvicorn app:app --host 127.0.0.1 --port 7860
```

`curl -s http://127.0.0.1:7860/health` harus melaporkan `model_status: candidate`
dan `prediction_enabled: true`. Contoh `POST /predict`, contoh respons, pilihan
kandidat lain, serta langkah training ulang ada di
[README backend](deploy/model-space/README.md).

Kandidat TBscreen (`training-output-residual/`) berada di luar Git, jadi di mesin
baru harus dilatih ulang lebih dulu dengan langkah di README backend.

Kemudian buat `.env.local` pada root project:

```env
BACKEND_API_URL=http://127.0.0.1:7860
ALLOW_DEMO_MODE=false
```

Jalankan `npm run dev`, buka `http://localhost:3000/analyze`, dan pilih
`Kenya (cohort model kandidat)` saat mengisi form. Endpoint `POST /predict`
menerima `audio` (PCM WAV) dan `metadata` (JSON string). Backend harus tetap
melaporkan `model_status: candidate`; konfigurasi ini hanya untuk pengujian lokal,
bukan deployment publik atau keputusan medis. `DEPLOYMENT_ENV=production`
selalu menolak manifest kandidat meskipun `ALLOW_BLOCKED_CANDIDATE=true`.
Frontend production juga menolak membuat skor simulasi bila backend tidak tersedia.
Kandidat residual terbaru tetap diblokir: nested cross-validation pada 70 subjek
menghasilkan pooled AUROC 0,639; operating point sensitif masih melewatkan 6/37
subjek TB dan salah merujuk 24/33 subjek non-TB. Karena belum ada validasi
eksternal, model tidak boleh diaktifkan untuk publik.

## Audit dan training GPU terbaru

Audit checkpoint, perbandingan ulang dengan split pasien yang sama, dan kandidat
AST pretrained baru sudah dijalankan pada RTX 4060 Laptop GPU. Hasil 3-fold pada
1.039 pasien CODA: CNN fusion v3 AUROC **0,810**, v4 **0,804**, clinical-only
**0,792**, AST+clinical baru **0,761**, dan AST audio-only **0,671**. Kandidat
baru belum mengalahkan v3; tidak ada klaim algoritma nomor satu dunia.

Artifact riset baru berada di `coda-tb/benchmark-ast-v1/candidate/`, dengan
encoder safetensors lokal di direktori `ast_model/` pada output yang sama.
Inference riset CPU/GPU sudah diuji; model tidak dipasang otomatis ke backend
production, skor belum terkalibrasi, dan gate tetap `blocked`. Satu checkpoint
historis (`output-long-fixed`) memiliki hash berbeda dari manifest.

Lihat [laporan audit dan protokol reproduksi](docs/MODEL_AUDIT_2026-10-03.md)
untuk interval ketidakpastian, confusion matrix, keterbatasan, dan log training.

## Pembayaran (opsional)

Tanpa `MIDTRANS_SERVER_KEY`, checkout tidak aktif dan analisis tetap gratis.
Setelah kredensial terpasang, satu analisis dibayar Rp5.000 melalui QRIS
Midtrans. Mekanismenya — verifikasi webhook, idempotensi, persetujuan
eksperimental, dan aturan kredit — ada di
[dokumentasi pembayaran](docs/BILLING.md).

Kredit hanya terpakai bila backend benar-benar mengembalikan skor, dan order
milik akun lain tidak bisa dipakai. Status validasi model tidak berubah karena
pengguna membayar.

## Integrasi SatuSehat (Sandbox)

Fitur rujukan dokter (`/rujukan`) menggunakan **data contoh bergaya SatuSehat sandbox**. Ini bukan koneksi ke API SatuSehat yang sesungguhnya — hanya simulasi UI untuk menunjukkan alur rujukan. Data faskes dan dokter bersifat fiktif.

Untuk integrasi SatuSehat Production di masa depan, diperlukan:
- Registrasi aplikasi di [SatuSehat Developer Portal](https://satusehat.kemkes.go.id/)
- OAuth2 client credentials
- Endpoint FHIR R4 untuk Practitioner, Organization, dan Encounter

## Struktur Proyek

```
src/
  app/            # Next.js App Router pages & API routes
  components/     # React components (landing, recorder, referral, dll.)
  lib/            # Utilities, types, API helpers
  hooks/          # Custom React hooks
  models/         # Auth models
  services/       # Referral service (sandbox)
public/
  models/lung.glb # Model 3D paru-paru
deploy/
  model-space/    # FastAPI backend + PyTorch model
docs/
  assets.md       # Asset disclosure log
```

---

## Kredit, Sumber & Lisensi

### Library & Framework

| Library | Versi | Lisensi | Sumber |
|---|---|---|---|
| [Next.js](https://nextjs.org/) | 16.3.3 | MIT | Vercel |
| [React](https://react.dev/) | 19.2.4 | MIT | Meta |
| [Three.js](https://threejs.org/) | 0.185.1 | MIT | mrdoob |
| [React Three Fiber](https://docs.pmnd.rs/react-three-fiber) | 9.6.1 | MIT | pmndrs |
| [@react-three/drei](https://github.com/pmndrs/drei) | 10.7.7 | MIT | pmndrs |
| [Tailwind CSS](https://tailwindcss.com/) | 4.x | MIT | Tailwind Labs |
| [Framer Motion](https://www.framer.com/motion/) | 12.42.2 | MIT | Framer |
| [Firebase](https://firebase.google.com/) | 12.16.0 | Apache-2.0 | Google |
| [clsx](https://github.com/lukeed/clsx) | 2.1.1 | MIT | Luke Edwards |
| [tailwind-merge](https://github.com/dcastil/tailwind-merge) | 3.6.0 | MIT | Dany Castillo |
| [tw-animate-css](https://github.com/nicholasgriffintn/tw-animate-css) | 1.4.0 | MIT | Nicholas Griffin |

### Backend ML

| Library | Lisensi | Sumber |
|---|---|---|
| [PyTorch](https://pytorch.org/) | BSD-3-Clause | Meta AI |
| [FastAPI](https://fastapi.tiangolo.com/) | MIT | Sebastián Ramírez |
| [NumPy](https://numpy.org/) | BSD-3-Clause | NumPy contributors |
| [pytest](https://pytest.org/) | MIT | pytest contributors |

`transformers` **tidak** ada di `requirements.txt`. Ia hanya dibutuhkan bila
menjalankan distillation (`src/pretrained_audio.py`), dan sengaja tidak ikut
terpasang agar runtime model tetap ringan — lihat `docs/RESEARCH_ROADMAP.md` §Fase 2.

### Font

| Font | Lisensi | Sumber |
|---|---|---|
| [Instrument Serif](https://fonts.google.com/specimen/Instrument+Serif) | OFL-1.1 | Rodrigo Fuenzalida / Instrument |
| [Plus Jakarta Sans](https://plusjakarta.id/) | OFL-1.1 | Tokotype |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | OFL-1.1 | JetBrains |

Ketiganya SIL Open Font License 1.1: boleh dipakai untuk aplikasi komersial,
termasuk di dalam produk berbayar, asal font tidak dijual terpisah, teks lisensi
ikut disertakan, dan nama font tidak dipakai tanpa izin. Font dikirim dari
`next/font` sehingga tidak ada permintaan ke pihak ketiga saat runtime.
Instrument Serif hanya punya satu Prelude (400) plus miring, jadi setiap aturan
display di `src/app/globals.css` dikunci di weight 400 agar tidak memunculkan
faux-bold.

### Aset 3D

| Aset | Lisensi | Sumber |
|---|---|---|
| `public/models/lung.glb` — Model 3D paru-paru | CC-BY 4.0 | [Human Reference Atlas 3D Reference Object Library](https://humanatlas.io/3d-reference-library) / NIH Visible Human Male, via `cns-iu/hra-amap` |

### Data & Statistik

- Statistik TB pada landing page bersumber dari **WHO Global Tuberculosis Report 2024**.
- Model audio kandidat dilatih dari nol menggunakan subset raw WAV **TBscreen** (publik, CC-BY 4.0; [Zenodo 10431329](https://doi.org/10.5281/zenodo.10431329), artikel [Science Advances 2024](https://doi.org/10.1126/sciadv.adi0282)). Pipeline lanjutan untuk CODA TB (CC-BY 4.0) ada di `training/cross_validate_fusion.py`; lihat `docs/DATASET_PROTOCOL.md`.
- Model belum lolos validasi eksternal; evaluation gate tetap diblokir dan hasil tidak boleh dipakai untuk diagnosis.
- Rujukan lengkap, jejak keputusan, dan justifikasi angka ada di `docs/RESEARCH_ROADMAP.md`.

### Aset AI-Generated

| Aset | Tool / Model | Catatan |
|---|---|---|
| `public/images/xai-from-scratch.png` | Dihasilkan dari model from-scratch kami | Peta sensitivitas occlusion untuk narasi sains |

### Referensi Desain

Tidak ada aset referensi eksternal yang disertakan. Seluruh komponen visual
dibuat sendiri di `src/`; tidak ada dependensi pada pustaka komponen pihak
ketiga (lihat tabel dependensi di atas).

---

## Disclaimer

> **Fitur ini adalah prototipe untuk hackathon dan bukan diagnosis medis.**
> Skor model tidak menggantikan pemeriksaan dokter, tes dahak, tes molekuler, atau rontgen dada.
> Untuk gejala atau kekhawatiran kesehatan, konsultasikan ke tenaga medis profesional.
>
- **Pembayaran tidak mengubah status validasi model.** Membayar Rp5.000 membeli satu
> kali analisis prototipe, bukan diagnosis dan bukan izin memakai layanan medis.
> Model belum tervalidasi eksternal dan belum pernah diuji pada peserta Indonesia.

## Lisensi

Proyek ini dibuat untuk GarudaHacks 7.0 Hackathon. Kode sumber menggunakan lisensi MIT kecuali dinyatakan lain pada aset individual.
