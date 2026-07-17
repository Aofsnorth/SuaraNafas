# Deteksi TB - GarudaHacks 7.0

Web app untuk deteksi dini tuberkulosis (TB) melalui analisis rekaman suara batuk.

## Tech Stack
- Next.js (App Router)
- TypeScript
- Tailwind CSS
- React Three Fiber / Three.js (Visualisasi 3D)

## Setup & Instalasi

1. **Clone repository & masuk ke direktori proyek:**
   ```bash
   cd "Hackathon Garuda Hacks 7.0"
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Konfigurasi Environment (Opsional):**
   Buat file `.env.local` di root jika ingin menghubungkan ke backend CNN:
   ```env
   BACKEND_API_URL=https://your-cnn-backend.example.com
   ```

4. **Jalankan server development:**
   ```bash
   npm run dev
   ```
   Aplikasi akan berjalan di [http://localhost:3000](http://localhost:3000).

## Build untuk Production

```bash
npm run build
npm run start
```
