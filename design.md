# Design — GarudaHacks 7.0 Deteksi TB

Sistem visual normatif untuk seluruh aplikasi. Setiap halaman dan komponen baru harus mengikuti file ini. `tokens.css` adalah representasi runtime dan harus mencerminkan nilai canonical di file ini.

## System

- Genre: custom technical-atmospheric.
- Vibe: dark clinical midnight, acoustic signal field, restrained optical glass.
- Axes: dark / roman-serif / neutral-silver.
- Referensi navbar: `assets/navbar-galery/desktop.webp`, dipakai sebagai inspirasi struktur dan ritme saja.
- Marketing: Marquee Hero menuju Signal Narrative.
- App: Workbench.
- Content: Long Document.
- Navigation: gallery-inspired compact three-zone bar.
- Footer: statement close dengan colophon ringkas.

Convex liquid glass merupakan pengecualian terkontrol dari atmospheric UI. Gunakan material ini hanya pada recorder, hasil analisis, data penting, workflow, dan specimen 3D. Narasi, manifesto, heading, dan sebagian besar copy tetap berada di kanvas terbuka.

## Tokens

```css
:root {
  --color-paper: oklch(11% 0.022 250);
  --color-paper-2: oklch(15% 0.028 250);
  --color-paper-3: oklch(20% 0.035 250);
  --color-ink: oklch(95% 0.012 235);
  --color-ink-2: oklch(76% 0.01 255);
  --color-rule: oklch(31% 0.006 255);
  --color-rule-2: oklch(39% 0.006 255);
  --color-control-border: oklch(64% 0.01 255);
  --color-muted: oklch(62% 0.01 255);
  --color-accent: oklch(80% 0.01 255);
  --color-accent-2: oklch(68% 0.01 255);
  --color-accent-ink: oklch(12% 0.025 250);
  --color-focus: oklch(86% 0.014 255);
  --color-error: oklch(66% 0.19 25);
  --color-warning: oklch(79% 0.13 82);
  --color-success: oklch(73% 0.12 158);

  --space-3xs: 0.125rem;
  --space-2xs: 0.25rem;
  --space-xs: 0.5rem;
  --space-sm: 0.75rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2.5rem;
  --space-2xl: 4rem;
  --space-3xl: 6rem;
  --space-4xl: 9rem;

  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-md: 1.25rem;
  --text-lg: 1.5625rem;
  --text-xl: 1.953rem;
  --text-2xl: 2.441rem;
  --text-3xl: 3.052rem;
  --text-display: clamp(3rem, 6vw + 0.5rem, 5.5rem);

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro: 120ms;
  --dur-short: 220ms;
  --dur-long: 420ms;
  --dur-breath: 7200ms;

  --radius-panel: 1.75rem 0.625rem 1.5rem 0.875rem;
  --radius-card-a: 1.5rem 0.5rem 1.25rem 0.75rem;
  --radius-card-b: 0.5rem 1.5rem 0.75rem 1.25rem;
  --radius-card-c: 1.25rem 0.75rem 1.5rem 0.5rem;
  --radius-control: 0.25rem;

  --z-base: 1;
  --z-raised: 10;
  --z-sticky: 200;
  --z-modal: 400;
  --z-toast: 500;
  --z-tooltip: 600;
}
```

`--color-rule` dan `--color-rule-2` hanya untuk dekorasi. Input, button outline, dialog boundary, dan surface interaktif memakai `--color-control-border` atau accent agar batas bermakna mencapai kontras minimum 3:1. Status colours hanya menandai error, warning, success, dan backend risk state.

## Typography

- Display: Fraunces, roman, `SOFT` dan `WONK` aktif.
- Body/UI: Geist 400; gunakan 500 atau 600 hanya untuk kontrol dan penekanan singkat.
- Mono: JetBrains Mono untuk wordmark, status, angka, label sumber, dan metadata teknis.
- Headline utama: “Dengarkan paru-paru berbicara.”
- Headline memakai slow typographic breathing selama 7,2 detik melalui dua layer teks berukuran identik yang crossfade. Layout memakai ukuran layer terlebar agar axis font tidak menggeser baris.
- Body minimum 16 px dengan line-height 1.5–1.65 dan measure maksimal 65ch.
- Heading selalu roman. Jangan gunakan italic display atau gradient text.

## Surface hierarchy

- `panel`: blur dan convex depth paling kuat untuk recorder, hasil, dan specimen 3D.
- `card`: depth sedang untuk workflow dan data WHO.
- `note`: hampir datar untuk source note, disclaimer, dan status prototipe.
- Navbar tetap full-width, square-edged, dan tidak memakai floating glass container.
- Pointer sheen hanya aktif pada surface bernilai tinggi, perangkat fine-pointer, dan saat reduced motion tidak aktif.

## Page families

### Landing `/`

Navbar, marquee hero, context strip, why-sound narrative, workflow, specimen 3D, data WHO, case note fiktif, FAQ, final CTA, statement footer.

### Analyze `/analyze`

Workbench dengan background tenang. Recorder, upload, progress, hasil, error, dan rekomendasi berada dalam satu `panel`. Logika audio dan API tidak berubah.

### Transparency `/transparency`

Long Document dengan background paling tenang. Isi mencakup sumber aset, sumber data, alur audio, keterbatasan model, lisensi, dan disclaimer medis. Gunakan `note` hanya untuk ringkasan risiko utama.

## CTA voice

- Navbar CTA: outline cyan, tajam, 44 px minimum.
- Hero primary: cyan fill dengan `--color-accent-ink`, radius 4 px.
- Secondary: outline atau typographic link dengan underline/rule.
- Label CTA harus satu baris pada lebar 320–1920 px.
- Active state menekan 1 px. Focus ring muncul langsung tanpa animasi.

## Motion stance

- Ambient loops: flowing main waveform, spectrum bar dance, dan slow typographic breathing.
- Intensitas background (waveform, spectrum, glow, partikel) bereaksi terhadap scroll melalui CSS scroll-driven animation (`animation-timeline: scroll`), tanpa JavaScript scroll listener atau React state per frame.
- Contour dan grid tetap statis. Scan beam merupakan one-shot berkala dengan jeda panjang.
- Reveal memakai opacity dan translate maksimum 8 px. Motion hanya memakai transform dan opacity; hindari parallax kamera, bounce, card hover lift, dan animasi bentuk acak.
- Reduced motion membekukan waveform, spectrum, glow energy, breathing, auto-rotate, scan, dan pointer sheen menjadi statis.

## Accessibility and responsive rules

- Uji 320, 375, 414, dan 768 px.
- Target sentuh minimum 44 × 44 px.
- Navbar mobile mempertahankan wordmark dan CTA; tautan sekunder masuk ke panel full-width.
- Menu mobile memakai tombol nyata, `aria-expanded`, Escape, focus management, dan pengembalian fokus.
- `html` dan `body` memakai `overflow-x: clip`.
- Kontrol, CTA, dan nav link tidak boleh membungkus menjadi dua baris.
- Warna bukan satu-satunya penanda error, success, atau risk.

## Content integrity

- Produk merupakan prototipe skrining awal, bukan alat diagnosis.
- Statistik harus menyebut metrik, tahun, definisi, dan sumber pada surface yang sama.
- Jangan mengklaim audio diproses lokal atau dihapus otomatis. Saat pengguna mengirim audio, route Next.js memproses mode mock atau meneruskannya ke backend yang dikonfigurasi.
- Route mock memakai copy tetap `Simulasi antarmuka. Audio yang dikirim tidak dianalisis untuk pola TB.` UI memetakan payload risk menjadi `Skenario simulasi A/B/C`, menampilkan `Nilai simulasi`, dan tidak merender label risiko atau pesan klinis dari payload mock.
- Jangan memakai testimonial, akurasi model, atau kutipan ilmiah tanpa sumber primer yang dapat diverifikasi.

## Exports

`tokens.css` dan Tailwind v4 `@theme inline` harus mencerminkan token di atas secara tepat. shadcn variables tetap memetakan `background`, `foreground`, `card`, `primary`, `border`, `input`, dan `ring` ke token canonical.