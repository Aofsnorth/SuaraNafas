# Clinical Midnight Redesign

**Status:** Approved design
**Date:** 2026-07-17
**Scope:** `/`, `/analyze`, `/transparency`, dan primitive visual bersama

## Summary

Redesign ini mengubah aplikasi menjadi pengalaman dark clinical midnight yang cocok untuk demo hackathon tanpa mengurangi kredibilitas medis. Landing page memakai struktur Signal Narrative. Halaman analisis memakai Workbench. Halaman transparansi memakai Long Document.

Referensi `assets/navbar-galery/desktop.webp` memberi arahan pada komposisi header: wordmark di kiri, navigasi di tengah, action di kanan, permukaan full-width, dan ruang yang tenang. Implementasi tidak menyalin warna, brand, mega-menu, atau detail khas referensi.

## Goals

- Membuat navbar lebih kuat dan lebih dekat dengan struktur referensi.
- Membuat background lebih hidup dengan satu bahasa visual akustik.
- Membangun convex liquid glass yang terkontrol dan reusable.
- Menjaga keterbacaan untuk pengguna muda maupun tua.
- Menyatukan visual landing, analyze, dan transparency tanpa mengubah kontrak backend.
- Menampilkan data TB dengan tahun, definisi, dan sumber yang terlihat.
- Menjaga status prototipe dan batas medis tetap jelas.

## Non-goals

- Mengubah endpoint `POST /api/analyze`, field `audio`, response shape `AnalysisResult`, atau perilaku forwarding backend. Copy mock dan validasi boundary boleh diperbaiki tanpa mengubah kontrak.
- Menambahkan library UI, state management, animation, atau testing baru.
- Menghapus route atau komponen produksi lama.
- Mengklaim akurasi, diagnosis, pemrosesan lokal, penghapusan audio, atau privasi yang belum diterapkan.
- Menyalin mega-menu atau identitas visual dari referensi publik.

## Locked design direction

- Genre: custom technical-atmospheric.
- Palette: dark clinical midnight dengan aksen cyan/ice-blue.
- Typography: Fraunces + Geist + JetBrains Mono.
- Landing macrostructure: Marquee Hero menuju Signal Narrative.
- Analyze macrostructure: Workbench.
- Transparency macrostructure: Long Document.
- Navbar: gallery-inspired compact three-zone bar.
- Footer: statement close dengan colophon.
- Card hierarchy: panel, card, note.
- Motion: ambient restrained.
- 3D lung: specimen sekunder, bukan hero.

Nilai token canonical berada di `design.md` dan harus dipindahkan ke `tokens.css` saat implementasi.

## Information architecture

### Landing `/`

1. **Navbar**
   - Wordmark `GARUDAHACKS / TB` hard-left.
   - Link `Cara kerja`, `Sains`, dan `FAQ` di tengah.
   - CTA `Mulai deteksi` hard-right.
   - Surface full-width tanpa floating pill.

2. **Hero**
   - Label prototipe singkat.
   - H1 `Dengarkan paru-paru berbicara.`
   - Lede menjelaskan skrining awal dari pola batuk dan pernapasan.
   - CTA `Mulai deteksi` dan `Lihat cara kerja →`.
   - Main waveform berada di belakang copy dengan mask kontras.
   - Tidak ada statistik raksasa di hero.

3. **Context strip**
   - `Prototipe hackathon`.
   - `Bukan diagnosis medis`.
   - `Data WHO dengan tahun dan definisi`.
   - `Mode demo bila backend belum terhubung`.

4. **Why sound**
   - Gabungkan manifesto dan statement menjadi narasi terbuka.
   - Jelaskan bahwa audio membawa pola frekuensi yang dapat dianalisis sebagai sinyal skrining.
   - Hindari klaim bahwa pola tersebut sudah tervalidasi sebagai diagnosis TB.

5. **Workflow**
   - `01 Rekam`, `02 Analisis`, `03 Pahami hasil`.
   - Gunakan tiga `card` dengan radius organik berulang.
   - Step 02 berdampingan dengan specimen 3D pada desktop.

6. **Science and 3D specimen**
   - Model paru tampil dalam satu `panel` besar.
   - Hotspot: Bronkus, Jaringan paru, Analisis AI.
   - Copy menjelaskan alur produk, bukan anatomi diagnostik.
   - Hapus kutipan “The Lancet Digital Health, 2023” sampai tim menyediakan artikel primer yang tepat.

7. **WHO data**
   - Tiga data card dengan definisi di surface yang sama.
   - Data tidak dipakai sebagai dekorasi atau headline hero.

8. **Case note**
   - Pertahankan contoh pasien dengan label `Fiktif` yang dominan.
   - Copy tidak menyiratkan hasil klinis nyata.

9. **FAQ**
   - Native `details` dan `summary`.
   - Pertanyaan membahas diagnosis, audio, mode demo, dan akurasi.

10. **Final CTA and footer**
    - CTA tunggal menuju `/analyze`.
    - Footer statement: prototipe hackathon dan bukan diagnosis medis.
    - Tautan transparansi dan sumber WHO tetap mudah ditemukan.

### Analyze `/analyze`

- Pakai background variant `app` dengan waveform samar, satu glow, dan tanpa constellation atau bentuk acak.
- Heading dan disclaimer berada di luar panel recorder.
- Semua recorder states berada dalam satu `ConvexSurface` variant `panel`.
- Status utama memakai `aria-live="polite"`.
- Error memakai pesan inline, ikon, warna, dan hubungan `aria-describedby`.
- Izin mikrofon yang ditolak tetap menyediakan jalur unggah file.
- File dan rekaman yang sudah dipilih tidak hilang ketika API gagal.
- Saat `source === "mock"`, abaikan risk label, message, dan recommendation klinis dari payload. Map `low/medium/high` ke `Skenario simulasi A/B/C`, render copy tetap `Simulasi antarmuka — audio tidak dianalisis`, tampilkan badge `Mode demo`, dan beri percentage label `Nilai simulasi`.
- Saat `source === "backend"`, label memakai `Skor model`. Jangan menyebut probability atau confidence terkalibrasi sampai backend mendokumentasikan kalibrasinya.
- Jangan mengubah request multipart, endpoint, atau response type.

### Transparency `/transparency`

Susun halaman sebagai Long Document dengan heading dan rules, bukan tumpukan kartu.

Bagian wajib:

- Status prototipe dan disclaimer medis.
- Cara audio mengalir: browser → `/api/analyze` → mock atau backend terkonfigurasi.
- Copy yang sama diringkas di dekat tombol kirim pada `/analyze`: `Audio dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.`
- Pernyataan bahwa aplikasi belum menjamin pemrosesan lokal atau penghapusan audio.
- Sumber model 3D dan lisensi CC-BY 4.0.
- Sumber WHO yang dipakai.
- Daftar visual code-built.
- Referensi navbar sebagai inspirasi publik, tidak digunakan sebagai aset produksi.

## Verified WHO data

Gunakan konstanta typed di `src/lib/tb-data.ts`.

```ts
interface TbDatum {
  value: string;
  label: string;
  definition: string;
  year: number;
  sourceTitle: string;
  sourceUrl: string;
  note?: string;
}
```

Data yang disetujui:

1. **10,8 juta**
   - Label: `Estimasi orang yang jatuh sakit akibat TB secara global`.
   - Tahun: 2023.
   - Definisi: estimasi insiden, bukan jumlah diagnosis yang dilaporkan.
   - Note: interval ketidakpastian WHO 10,1–11,7 juta; 134 kasus insiden per 100.000 penduduk.
   - Source: WHO Global Tuberculosis Report 2024, TB incidence.
   - URL: `https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-disease-burden/1-1-tb-incidence`.

2. **8,2 juta**
   - Label: `Orang dengan episode TB baru atau kambuh yang didiagnosis dan dinotifikasi`.
   - Tahun: 2023.
   - Definisi: new and relapse cases yang diagnosed and notified; bukan estimasi total insiden.
   - Source: WHO Global Tuberculosis Report 2024, Case notifications.
   - URL: `https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-diagnosis-and-treatment/2-1-case-notifications`.

3. **10%**
   - Label: `Perkiraan bagian Indonesia dari kasus insiden TB global`.
   - Tahun: 2023.
   - Definisi: proporsi estimasi kasus insiden TB global yang dikaitkan WHO dengan Indonesia.
   - Source: WHO, `Tuberculosis resurges as top infectious disease killer`, 29 October 2024.
   - URL: `https://www.who.int/news/item/29-10-2024-tuberculosis-resurges-as-top-infectious-disease-killer`.

Setiap card menampilkan value, label, year, definition, dan source link. Jangan menampilkan value tanpa label atau year.

## Component design

### `Navbar`

- Ubah menjadi client component untuk menu mobile dan scroll state.
- Gunakan `usePathname` agar link section selalu menuju `/#cara-kerja`, `/#sains`, dan `/#faq` saat navbar tampil di route lain.
- CTA menuju `/analyze`; pada `/analyze`, label berubah menjadi `Beranda` dan menuju `/` agar navbar tidak menawarkan aksi menuju halaman yang sedang aktif.
- Desktop memakai grid `1fr auto 1fr`.
- Centre links masuk ke dialog di bawah `60rem`; layout wordmark + short CTA + menu harus muat pada 320 px.
- Mobile mempertahankan wordmark dan CTA `Mulai`; link sekunder masuk ke native `dialog` full-width.
- Trigger memakai `aria-expanded`, `aria-controls`, dan target minimum 44 px.
- Dialog menutup lewat Escape, backdrop, tombol close, dan pilihan link.
- Setelah dialog menutup, fokus kembali ke trigger.
- Scroll state mengubah opacity surface, blur, dan rule bawah tanpa morph menjadi pill.

### `ConvexSurface`

File: `src/components/convex-surface.tsx`.

```ts
type ConvexSurfaceVariant = "panel" | "card" | "note";

interface ConvexSurfaceProps {
  children: React.ReactNode;
  className?: string;
  variant?: ConvexSurfaceVariant;
}
```

- `panel`: depth kuat untuk recorder, result, dan 3D.
- `card`: depth sedang untuk workflow dan data.
- `note`: hampir datar untuk disclaimer dan source note.
- `ConvexSurface` tetap server-compatible dan tidak memiliki event handler.
- Client component kecil `ConvexSheen` hanya dipasang pada recorder, result, dan 3D panel. Ia mengubah CSS custom properties melalui `requestAnimationFrame` tanpa React state per pointer move.
- Aktifkan sheen hanya dalam `@media (hover: hover) and (pointer: fine)`.
- Reduced motion menonaktifkan sheen.
- Mobile memakai blur lebih rendah dan surface lebih opaque. `@supports not (backdrop-filter: blur(1px))` memakai opaque `paper-2`/`paper-3` fallback.
- Jangan memakai hover translate atau scale.

### `BreathingHeadline`

File: `src/components/breathing-headline.tsx`.

- Render server-side; tidak memakai interval JavaScript.
- Satu heading semantic menyediakan accessible name.
- Dua visual layers identik memakai `aria-hidden="true"` dan crossfade opacity selama 7,2 detik antara dua kombinasi `SOFT/WONK`.
- Container mengambil ukuran layer terlebar; verifikasi tidak ada perubahan line wrap atau layout shift.
- Reduced motion menampilkan satu layer statis.

### `AtmosphericBackground`

Tambahkan prop:

```ts
type BackgroundVariant = "landing" | "app" | "document";
```

- `landing`: main waveform, one echo field, contour lines, clinical grid, two static glows, one-shot scan beam, maksimal 18 static particles.
- `app`: waveform samar, one static glow, clinical grid, maksimal 6 static particles.
- `document`: static gradient, noise, dan rule grid yang sangat samar.
- Hapus abstract shapes, floating lines, constellation, floating orbs, dan echo layers berlebih.
- Maksimal dua ambient loops: main waveform dan headline breathing. Scan beam memakai one-shot animation dengan jeda panjang.

`Background` menerima `variant: "app" | "document"`. `/analyze` memakai `app`; `/transparency` memakai `document`.

### `TbDataSection`

File: `src/components/tb-data-section.tsx`.

- Server component.
- Membaca `TB_DATA` dari `src/lib/tb-data.ts`.
- Card order mengikuti konteks: estimated incidence, reported diagnoses, Indonesia share.
- Source link memiliki nama dokumen yang jelas, bukan `klik di sini`.

### Mock API copy

`src/app/api/analyze/route.ts` mempertahankan kontrak dan deterministic scenario selection, tetapi mock response tidak boleh menyatakan bahwa audio dianalisis. Semua mock payloads memakai pesan dan rekomendasi non-klinis:

- `message`: `Simulasi antarmuka. Audio yang dikirim tidak dianalisis untuk pola TB.`
- `recommendation`: `Hubungkan backend tervalidasi untuk memperoleh output model. Untuk kekhawatiran kesehatan, konsultasikan ke tenaga medis.`

Backend responses tetap diteruskan tanpa rewrite selain `source: "backend"`.

### `AudioRecorder`

- Pertahankan hooks dan flow yang ada.
- Ganti surface menjadi `ConvexSurface` variant `panel`.
- Kelompokkan status, waveform, actions, selected file, processing, result, dan disclaimer dengan hierarchy yang konsisten.
- Gunakan label action satu baris.
- Error region memakai `role="alert"`.
- Processing region memakai `aria-live="polite"`.
- Tampilkan mock result sebagai `Skenario simulasi A/B/C`; jangan merender label `Risiko rendah/sedang/tinggi` atau message/recommendation klinis dari payload mock.
- Tampilkan disclosure audio tepat di dekat action kirim: `Audio dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.`

### `LungModel`

- Tetap lazy-loaded melalui `next/dynamic` dengan `ssr: false`.
- `LungModelWrapper` memakai IntersectionObserver dan hanya merender dynamic `LungModel` setelah specimen mendekati viewport.
- Hapus atau gate unconditional `useGLTF.preload()` agar file GLB tidak diambil sebelum intersection.
- Deteksi WebGL sebelum render; tampilkan fallback tekstual bila tidak tersedia.
- Resolve warna model dari CSS tokens melalui adapter browser, bukan menduplikasi warna brand di banyak file.
- Ubah material menjadi translucent ice-blue.
- Reduced motion mematikan auto-rotate, hover scale, dan emissive pulse.
- Hotspot memakai sharp compact controls dengan target 44 px.

### `Footer`

- Gunakan Ft5 Statement.
- Statement singkat menutup narasi.
- Colophon memuat tim, sumber WHO, lisensi model, transparency link, dan disclaimer.
- Jangan memakai grid link generik.

## Interaction states

State requirements mengikuti fungsi kontrol:

- Buttons dan upload action: default, hover, focus, active, disabled, loading bila memulai proses.
- Recorder dan analysis action: error dan success hanya ketika state tersebut relevan.
- Navigation links: default, hover, focus, active, dan `aria-current`.
- FAQ: closed, open, hover, dan focus.
- Hotspots: default, hover, focus, selected/open, serta unavailable fallback.
- Semua error memakai icon/text dan ARIA, bukan warna saja. Success tetap tenang tanpa toast perayaan.

## Motion rules

- Headline breathing: 7200 ms opacity crossfade antara dua layer metric-contained.
- Main waveform: 18–24 s per loop.
- Particles, contour, grid, dan glows statis.
- Scan beam: one-shot berdurasi pendek dengan jeda panjang; opacity rendah.
- Menu open: 220 ms; close sekitar 165 ms.
- Reveal: 420 ms, translate maksimum 8 px, total stagger maksimum 360 ms.
- Card pointer sheen: opacity and position only; no element lift.
- Reduced motion: opacity-only maksimal 150 ms, tanpa auto-rotate atau ambient loop.

## Accessibility

- WCAG 2.1 AA minimum.
- Body target contrast 7:1; minimum 4.5:1.
- UI boundary dan focus target minimum 3:1. Meaningful boundaries memakai `--color-control-border`; token ini terverifikasi 5,26:1 pada paper, 5,05:1 pada paper-2, dan 4,65:1 pada paper-3.
- Heading order tidak melompat.
- Semua section anchors memiliki scroll margin untuk navbar fixed.
- Touch target minimum 44 × 44 px.
- Uji keyboard untuk navbar, dialog mobile, recorder, upload, FAQ, result reset, dan hotspots.
- CTA dan nav label tidak membungkus pada 320–1920 px.
- Uji viewport 320, 375, 414, 768, 960, dan 1440 px.

## Performance

- Tidak menambah dependency.
- Pertahankan `next/font`.
- Hero tidak memakai model 3D atau image berat.
- Model 3D dimuat dekat viewport.
- Background tidak memakai canvas atau scroll listener.
- Gunakan transform dan opacity untuk animasi utama. Headline breathing merupakan crossfade dua layer metric-contained; jangan menganimasikan layout atau satu layer teks yang berubah lebar.
- Jangan memakai React state untuk setiap frame background atau pointer move.
- Target tidak menambah layout shift pada font, navbar, recorder, atau model placeholder.

## Error and fallback behaviour

- Microphone denied: tampilkan pesan yang dapat ditindaklanjuti dan opsi upload.
- Recorder error: stop tracks dan tampilkan inline alert.
- API error: pertahankan selected audio dan action retry.
- Backend unreachable: tampilkan pesan route yang ada tanpa mengubah mode menjadi mock secara diam-diam.
- Mock mode: route mengembalikan copy simulasi non-klinis; UI tetap mengabaikan message/recommendation payload mock sebagai defence in depth.
- WebGL unavailable atau model gagal: fallback menjelaskan tiga tahap analisis tanpa ruang kosong.
- Reduced motion: semua informasi tetap tersedia.
- JavaScript belum siap: server-rendered content landing dan transparency tetap terbaca.

## File plan

### Already created or updated during design

- `design.md` — normative design system; preserve and implement against it.
- `AGENTS.md` — approved redesign override.
- `docs/superpowers/specs/2026-07-17-clinical-midnight-redesign-design.md` — this specification.

### Create

- `src/components/convex-surface.tsx`
- `src/components/convex-sheen.tsx`
- `src/components/breathing-headline.tsx`
- `src/components/tb-data-section.tsx`
- `src/lib/tb-data.ts`

### Edit

- `tokens.css`
- `src/app/globals.css`
- `src/components/Navbar.tsx`
- `src/components/Landing.tsx`
- `src/components/AtmosphericBackground.tsx`
- `src/components/Background.tsx`
- `src/components/AudioRecorder.tsx`
- `src/components/AsciiHero.tsx`
- `src/components/GlassCard.tsx`
- `src/components/Bento.tsx`
- `src/components/CaseFile.tsx`
- `src/components/Faq.tsx`
- `src/components/Hero.tsx`
- `src/components/LabStrip.tsx`
- `src/components/Manifesto.tsx`
- `src/components/Science.tsx`
- `src/components/Statement.tsx`
- `src/components/Stats.tsx`
- `src/components/Workflow.tsx`
- `src/components/LungModel.tsx`
- `src/components/LungModelWrapper.tsx`
- `src/components/Footer.tsx`
- `src/app/analyze/page.tsx`
- `src/app/transparency/page.tsx`
- `src/app/api/analyze/route.ts` — replace mock copy only; preserve endpoint, field, response shape, deterministic demo selection, and backend forwarding.
- `docs/assets.md`
- `.hallmark/log.json` — prepend one entry: `{ "date": "2026-07-17", "scope": "app", "macrostructure": "Marquee Hero → Signal Narrative / Workbench / Long Document", "theme": "custom", "theme_axes": "dark / roman-serif / cool-cyan", "vibe": "dark clinical midnight, acoustic signal field, restrained optical glass", "enrichment": "Tier-B acoustic signal field + lazy 3D specimen", "brief": "GarudaHacks TB multi-page clinical midnight redesign" }`.
- `.gitignore` already updated during design to ignore `/.superpowers/` Visual Companion artifacts.

### Preserve

- `src/lib/api.ts`
- `src/lib/types.ts`
- Recording and analysis hooks.
- Existing route tree.
- Existing route and component files. Do not delete them during this redesign. Legacy components listed under Edit must remove stale privacy/medical copy or delegate to the new primitives, even if they are no longer imported.

## Validation

Run in this order:

1. `npm run lint`.
2. `npm run build`.
3. Keyboard smoke test for three routes.
4. Recorder smoke test: permission request, record, stop, choose recording, analyze, reset.
5. Upload smoke test: select audio, analyze, retry after error.
6. Mock result check: permanent mode badge and simulation label.
7. Responsive checks at 320, 375, 414, 768, 960, and 1440 px.
8. Reduced-motion check.
9. WebGL fallback check.
10. Manual contrast and focus review.

The project has no automated test runner or browser E2E dependency. Do not add one for this visual redesign. Report manual checks separately from lint and build.

The existing API accepts any non-empty `File`; MIME, duration, and size limits are not defined by the backend contract. Do not invent silent limits in this redesign. Record production-grade upload validation as a launch prerequisite for the backend team.

## Acceptance criteria

- Navbar matches the reference’s three-anchor composition without copying its brand or mega-menu.
- Landing follows this measurable Signal Narrative order: marquee hero, context strip, open why-sound narrative, workflow + 3D specimen, verified WHO data, case note, FAQ, final CTA, statement footer.
- Hero contains no contextless epidemiology statistic.
- Convex glass follows the panel/card/note hierarchy.
- Narrative sections remain open and readable.
- Background has one coherent acoustic language and fewer random elements than the current implementation.
- All three routes share palette, typography, CTA voice, and navbar.
- Analyze and transparency use lower background intensity than landing.
- 3D lung remains below the fold and lazy-loaded.
- WHO cards show metric, year, definition, and source together; `tokens.css` matches every canonical token in `design.md`.
- Mock results state `Simulasi antarmuka — audio tidak dianalisis`, use neutral `Skenario simulasi A/B/C` and `Nilai simulasi`, and cannot be mistaken for clinical predictions.
- No UI claims local-only processing or automatic deletion.
- No production file or route is deleted.
- Lint and build pass after implementation.
- Keyboard, responsive, reduced-motion, and fallback smoke checks complete before handoff.
- Before production launch, the backend team records accepted audio MIME types, maximum bytes, maximum duration, rejection messages, and retention policy in the API contract; those limits receive boundary tests before release.