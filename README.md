# SuaraNafas — GarudaHacks 7.0

Web app untuk riset skrining tuberkulosis (TB) melalui analisis rekaman suara batuk menggunakan model CNN audio.

## Fitur Utama

- **Rekam / unggah audio** batuk langsung dari browser.
- **Analisis CNN audio** — model from-scratch yang membaca fitur log-mel spectrogram tanpa bobot pretrained.
- **Visualisasi 3D** paru-paru interaktif berbasis React Three Fiber.
- **Referral sandbox** bergaya SatuSehat — daftar contoh dokter/faskes untuk simulasi rujukan (data sandbox, bukan faskes nyata).
- **Mode demo** — jika backend belum terhubung, hasil simulasi ditampilkan dengan label "Mode demo".

## Tech Stack

| Layer | Teknologi |
|---|---|
| Framework | Next.js 16 (App Router) |
| Bahasa | TypeScript |
| Styling | Tailwind CSS v4 |
| Komponen UI | shadcn/ui (base-nova preset) |
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

### Konfigurasi Environment (Opsional)

Buat file `.env.local` di root:

```env
# Opsional. Jika di-set, /api/analyze meneruskan request ke backend CNN.
BACKEND_API_URL=https://your-cnn-backend.example.com
```

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

## Backend ML (`deploy/model-space`)

Mode default menolak checkpoint yang belum lolos validasi eksternal. Untuk menguji
checkpoint kandidat lokal secara eksplisit:

```bash
cd deploy/model-space
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
MODEL_MANIFEST_PATH=training-output/manifest-audio.json \
ALLOW_BLOCKED_CANDIDATE=true \
uvicorn app:app --host 127.0.0.1 --port 7860
```

Kemudian buat `.env.local` pada root project:

```env
BACKEND_API_URL=http://127.0.0.1:7860
```

Jalankan `npm run dev`, buka `http://localhost:3000/analyze`, dan pilih
`Kenya (cohort model kandidat)` saat mengisi form. Endpoint `POST /predict`
menerima `audio` (PCM WAV) dan `metadata` (JSON string). Backend harus tetap
melaporkan `model_status: candidate`; konfigurasi ini hanya untuk pengujian lokal,
bukan deployment publik atau keputusan medis.

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
| [shadcn/ui](https://ui.shadcn.com/) | 4.13.0 | MIT | shadcn |
| [Lucide React](https://lucide.dev/) | 1.24.0 | ISC | Lucide Contributors |
| [Firebase](https://firebase.google.com/) | 12.16.0 | Apache-2.0 | Google |
| [clsx](https://github.com/lukeed/clsx) | 2.1.1 | MIT | Luke Edwards |
| [tailwind-merge](https://github.com/dcastil/tailwind-merge) | 3.6.0 | MIT | Dany Castillo |
| [class-variance-authority](https://cva.style/) | 0.7.1 | Apache-2.0 | Joe Bell |
| [tw-animate-css](https://github.com/nicholasgriffintn/tw-animate-css) | 1.4.0 | MIT | Nicholas Griffin |
| [@base-ui/react](https://base-ui.com/) | 1.6.0 | MIT | MUI |

### Backend ML

| Library | Lisensi | Sumber |
|---|---|---|
| [PyTorch](https://pytorch.org/) | BSD-3-Clause | Meta AI |
| [FastAPI](https://fastapi.tiangolo.com/) | MIT | Sebastián Ramírez |

| [NumPy](https://numpy.org/) | BSD-3-Clause | NumPy contributors |

### Font

| Font | Lisensi | Sumber |
|---|---|---|
| [Fraunces](https://github.com/undercasetype/Fraunces) | OFL-1.1 | Undercase Type |
| [Geist](https://vercel.com/font) | OFL-1.1 | Vercel |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | OFL-1.1 | JetBrains |

### Aset 3D

| Aset | Lisensi | Sumber |
|---|---|---|
| `public/models/lung.glb` — Model 3D paru-paru | CC-BY 4.0 | [Human Reference Atlas 3D Reference Object Library](https://humanatlas.io/3d-reference-library) / NIH Visible Human Male, via `cns-iu/hra-amap` |

### Data & Statistik

- Statistik TB pada landing page bersumber dari **WHO Global Tuberculosis Report 2024**.
- Model audio kandidat dilatih dari nol menggunakan subset raw WAV **TBscreen** (publik, CC-BY 4.0; [Zenodo 10431329](https://doi.org/10.5281/zenodo.10431329)).
- Model belum lolos validasi eksternal; evaluation gate tetap diblokir dan hasil tidak boleh dipakai untuk diagnosis.

### Aset AI-Generated

| Aset | Tool / Model | Catatan |
|---|---|---|
| `assets/chatgpt-image/image.png` | Tidak tercatat | Eksplorasi desain, tidak digunakan di production |
| `public/images/xai-from-scratch.png` | Dihasilkan dari model from-scratch kami | Peta sensitivitas occlusion untuk narasi sains |

### Referensi Desain

- `assets/navbar-galery/desktop.webp` — referensi layout navbar. Hanya digunakan sebagai inspirasi, tidak dikirim ke production.

---

## Disclaimer

> **Fitur ini adalah prototipe untuk hackathon dan bukan diagnosis medis.**
> Skor model tidak menggantikan pemeriksaan dokter, tes dahak, tes molekuler, atau rontgen dada.
> Untuk gejala atau kekhawatiran kesehatan, konsultasikan ke tenaga medis profesional.

## Lisensi

Proyek ini dibuat untuk GarudaHacks 7.0 Hackathon. Kode sumber menggunakan lisensi MIT kecuali dinyatakan lain pada aset individual.
