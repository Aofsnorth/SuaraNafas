# SuaraNafas — GarudaHacks 7.0

Web app untuk deteksi dini tuberkulosis (TB) melalui analisis rekaman suara batuk menggunakan model CNN multimodal.

## Fitur Utama

- **Rekam / unggah audio** batuk atau pernapasan langsung dari browser.
- **Analisis CNN** — model multimodal yang menggabungkan fitur akustik (mel-spectrogram) dengan metadata klinis.
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

## Backend ML (deploy/model-space)

```bash
cd deploy/model-space
pip install -r requirements.txt
python export_deployment_config.py   # generate deployment_config.json
uvicorn app:app --host 0.0.0.0 --port 7860
```

Endpoint: `POST /predict` — menerima `audio` (file) + `metadata` (JSON string berisi data klinis).

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
| [Next.js](https://nextjs.org/) | 16.2.10 | MIT | Vercel |
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
| [librosa](https://librosa.org/) | ISC | librosa contributors |
| [soundfile (PySoundFile)](https://github.com/bastibe/python-soundfile) | BSD-3-Clause | Bastian Bechtold |
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
- Data klinis model menggunakan dataset **CODA-TB** (publik).

### Aset AI-Generated

| Aset | Tool / Model | Catatan |
|---|---|---|
| `assets/chatgpt-image/image.png` | Tidak tercatat | Eksplorasi desain, tidak digunakan di production |
| `public/images/test_xai_output.png` | User-supplied | Visualisasi XAI untuk narasi sains |

### Referensi Desain

- `assets/navbar-galery/desktop.webp` — referensi layout navbar. Hanya digunakan sebagai inspirasi, tidak dikirim ke production.

---

## Disclaimer

> **Fitur ini adalah prototipe untuk hackathon dan bukan diagnosis medis.**
> Hasil skrining tidak menggantikan pemeriksaan dokter, tes dahak, tes molekuler, atau rontgen dada.
> Untuk gejala atau kekhawatiran kesehatan, konsultasikan ke tenaga medis profesional.

## Lisensi

Proyek ini dibuat untuk GarudaHacks 7.0 Hackathon. Kode sumber menggunakan lisensi MIT kecuali dinyatakan lain pada aset individual.
