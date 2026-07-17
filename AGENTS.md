# AGENTS.md — GarudaHacks7.0-Deteksi-TB

## Project Context

- Build a web app for early TB detection through cough audio analysis.
- **Current focus: frontend landing page + CNN integration skeleton** — data-led, anti-AI-slop landing page with a functional `/analyze` prototype that records/uploads audio and returns a simulated UI result until the backend is ready.
- The AI/ML pipeline and backend are being built by teammates; the frontend exposes a clear API contract and can forward requests to their backend.
- This file guides any AI agent or contributor working on the frontend.

## Tech Stack

- **Framework:** Next.js 16 with App Router (`app/` directory).
- **Language:** TypeScript.
- **Styling:** Tailwind CSS v4 (CSS-first configuration via `globals.css` and `postcss.config.mjs`).
- **UI Components:** shadcn/ui base-nova preset (install components as needed; avoid adding external UI libraries).
- **Fonts:** `next/font/google`.
  - Display/headings: **Fraunces** (with `SOFT` + `WONK` axes for organic, hand-set feel).
  - Body/UI: **Geist**.
  - Mono/technical accents: **JetBrains Mono**.
- **3D:** React Three Fiber, Three.js, Drei (`@react-three/fiber`, `three`, `@react-three/drei`).
- **Animation:** Framer Motion (used sparingly for the 3D hotspots only).
- **Icons:** Prefer hand-rolled SVG or a single icon library. Do not mix icon sets.
- **State:** React hooks for local state. No external state library for the MVP.
- **Package manager:** npm (pnpm is preferred but not available in this environment).
- **Deployment target:** Vercel.

## Getting Started

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Approved Redesign Override — 2026-07-17

The approved system in `design.md` and `docs/superpowers/specs/2026-07-17-clinical-midnight-redesign-design.md` supersedes the older visual requirements in **Design Direction**, **Color Tokens**, **MVP Landing Page Specification**, **Hero Copy**, and the navbar rules below.

Use these current requirements:

- Custom technical-atmospheric **Dark Clinical Midnight** palette with cool cyan accent.
- Landing macrostructure: **Marquee Hero → Signal Narrative**.
- Hero headline: `Dengarkan paru-paru berbicara.`; do not place a contextless epidemiology statistic in the hero.
- Gallery-inspired compact navbar: wordmark left, `Cara kerja` / `Sains` / `FAQ` centre, `Mulai deteksi` right; mobile moves secondary links into a full-width dialog.
- Controlled convex surfaces for recorder, results, workflow, verified WHO data, and the 3D specimen. Narrative sections remain open.
- Landing uses the strongest acoustic background; `/analyze` is calmer; `/transparency` is document-like.
- Mock responses must be labelled as UI simulation, must not claim that audio patterns were analysed, and must use neutral scenario labels rather than low/medium/high risk wording.

The older sections remain as project history and backend context. If they conflict with the approved redesign documents, the approved redesign wins.

## Design Direction

**Historical direction retained for context: anti-AI-slop, tactile, bio-digital dark medical UI.**

This is a deliberate departure from the previous generic glassmorphism hero. The new direction is built on 2026 anti-slop and tactile-rebellion principles: visible craft, human typography, honest data, organic imperfect shapes, and a restrained accent footprint.

- **Macrostructure:** Stat-Led — the page opens with a giant WHO-verified TB statistic.
- **Theme:** custom bio-digital moss, dark. Deep green-black paper (`oklch(15% 0.02 145)`), mycelium off-white ink, electric moss accent (`oklch(72% 0.22 135)`).
- **Typography:** Fraunces display with `WONK` axis enabled for an imperfect, hand-set feel; Geist body; JetBrains Mono for numerals and source notes.
- **Texture:** subtle SVG noise overlay + slow organic blob shapes for a tactile, "living" surface.
- **Shapes:** organic, asymmetric border-radius on stat cards; avoid uniform rounded corners and floating glass pills.
- **Motion:** CSS number reveal on the hero stat, heartbeat pulse on the 3D lung material, reduced-motion fallbacks everywhere. No generic `whileHover` lifts on every card.
- **Default to dark mode.** Do not build a light-mode toggle for the MVP.

### Color Tokens

Stored in `tokens.css` and wired into Tailwind v4 through `src/app/globals.css`.

```css
:root {
  --color-paper:    oklch(15% 0.02 145);
  --color-paper-2:  oklch(20% 0.025 145);
  --color-paper-3:  oklch(26% 0.03 145);
  --color-ink:      oklch(95% 0.01 120);
  --color-ink-2:    oklch(78% 0.015 130);
  --color-rule:     oklch(32% 0.025 145);
  --color-rule-2:   oklch(40% 0.025 145);
  --color-muted:    oklch(52% 0.02 135);
  --color-accent:   oklch(72% 0.22 135);
  --color-accent-ink: oklch(15% 0.02 145);
  --color-focus:    oklch(72% 0.22 135);
}
```

### Typography and Shape

- Headings: Fraunces, `font-variation-settings: "SOFT" 0, "WONK" 1`.
- Body/UI text: Geist, regular or medium.
- Mono/labels: JetBrains Mono, used for numerals, source notes, and the wordmark.
- Stat cards use organic `border-radius` values (not uniform `rounded-3xl`).
- CTA buttons are outlined chips with sharp corners (`rounded-sm`), not filled pills.
- Avoid italic headers; emphasis comes from weight, accent colour, or a drawn underline.

## Frontend Conventions

- **App Router first.** Use `src/app/`.
- **Server Components by default.** Add `'use client'` only for interactivity: 3D canvas, client animations, forms, client hooks.
- **Metadata:** export `metadata` from `src/app/layout.tsx` and any route `page.tsx`.
- **Class merging:** prefer the `cn()` helper from `lib/utils` for complex class compositions.
- **Component locations:**
  - `src/components/ui/` — shadcn/ui primitives.
  - `src/components/` — landing page components (Navbar, Hero, LabStrip, Stats, Manifesto, Statement, Workflow, Science, CaseFile, Faq, Footer, AudioSpectrum, LungModel, LungModelWrapper, Background).
- **Utilities:** `src/lib/` for helpers and constants.
- **Code style:**
  - File names: kebab-case.
  - Components: PascalCase.
  - Hooks, functions, variables: camelCase.
  - Constants: UPPER_SNAKE_CASE.
  - Do not add comments unless explicitly asked. Prefer self-explanatory names.
  - User-facing copy in **Bahasa Indonesia**; code, file names, and identifiers in **English**.
- **Accessibility:**
  - Minimum contrast 4.5:1 for normal text.
  - Touch targets at least 44 x 44 px.
  - Provide `aria-label` and keyboard focus states on interactive elements.
  - Support `prefers-reduced-motion` for any motion.
- **Performance:**
  - Use `next/font` for fonts.
  - Lazy-load the 3D scene with `next/dynamic` and `ssr: false`.
  - Keep client components minimal and co-located.
- **Responsive:** mobile-first. The 3D canvas should adapt to mobile viewports.

## MVP Landing Page Specification

### Page Structure

1. **Edge-aligned minimal Navbar** — wordmark hard-left, single CTA hard-right, no generic link row.
2. **Hero (Stat-Led)** — giant WHO statistic `10,8 juta`, qualifier, source note, typographic CTA.
3. **LabStrip** — full-bleed metadata band: WHO source, case count, country coverage, Indonesia burden, prototype status, medical disclaimer.
4. **Stats** — four asymmetric stat cards with real WHO data and source notes.
5. **Manifesto** — large typographic band: *Suara adalah sinyal. Deteksi awal adalah pertahanan pertama.*
6. **Statement** — a manifesto-like declaration on a dark paper-2 band with a marginalia aside.
7. **Workflow** — three numbered stages (Rekam → Analisis → Hasil); stage 1 shows a hand-built SVG waveform, stage 2 embeds the 3D lung model with a specimen label.
8. **Science** — pull-quote on acoustic AI screening with marginalia attribution.
9. **CaseFile** — a fictional patient vignette in document format, clearly labelled *Fiktif*.
10. **FAQ** — native `<details>`/`<summary>` accordion, honest answers, no marketing fluff.
11. **Footer** — dense typographic colophon with credits, WHO source links, and medical disclaimer.
12. **`/analyze`** — functional audio skrining prototype: record/upload cough or breathing audio, receive a risk prediction (mock while backend is in development).
13. **`/transparency`** — asset disclosure and medical disclaimer.

### Hero Copy

- Label: `GarudaHacks 7.0`
- Figure: `10,8 juta`
- Headline: `kasus tuberkulosis aktif tercatat setiap tahun di seluruh dunia.`
- Qualifier: `Hampir sepertiga tidak terdiagnosis. Deteksi dini adalah garis pertama untuk menghentikan penularan dan menyelamatkan nyawa.`
- Primary CTA: `Mulai deteksi` (links to `/analyze`)
- Secondary CTA: `Lihat cara kerja →`
- Source: `WHO Global Tuberculosis Report 2024`

Do **not** use absolute medical claims (e.g. 100% akurat, hasil instan, menjamin privasi). All statistics must be sourced from WHO publications.

### 3D Lung Model

- Source: `public/models/lung.glb` (Human Reference Atlas / NIH Visible Human Male, CC-BY 4.0).
- Rendered with React Three Fiber + Drei inside the workflow section, not the hero.
- Material: semi-transparent physical material with a procedural noise bump/roughness map and a subtle heartbeat emissive pulse.
- Interactions: rotate, drag, auto-rotate (disabled under `prefers-reduced-motion`), hover scale.
- Hotspots: Bronkus, Jaringan paru, Analisis AI — clickable, show a small popup with a short explanation.

## CNN Backend Integration

### API Contract

The frontend communicates with the backend through the Next.js API route `app/api/analyze/route.ts`. This keeps the client decoupled from the real backend URL and lets the team develop the UI before the backend is live.

- **Client → Next.js API**
  - `POST /api/analyze`
  - `Content-Type: multipart/form-data`
  - Field: `audio` (Blob/File containing cough or breathing audio)
  - Response shape: `AnalysisResult`

- **Next.js API → Backend**
  - If `BACKEND_API_URL` is set, the route forwards the file to `POST ${BACKEND_API_URL}/predict` with the same `multipart/form-data` payload.
  - The backend should respond with JSON matching the `AnalysisResult` interface.

- **Mock Mode**
  - If `BACKEND_API_URL` is not set, the route returns a deterministic mock response based on the uploaded file size. The response includes `source: "mock"` so the UI can show a "mode demo" indicator.

### AnalysisResult Type

```ts
// src/lib/types.ts
export type RiskLevel = "low" | "medium" | "high";

export interface AnalysisResult {
  risk: RiskLevel;
  confidence: number;      // 0.0 – 1.0
  message: string;          // human-readable explanation in Indonesian
  recommendation: string;     // actionable next step in Indonesian
  source?: "mock" | "backend";
}
```

### Environment Variables

```bash
# .env.local
# Optional. When set, /api/analyze forwards requests to the backend.
BACKEND_API_URL=https://your-cnn-backend.example.com
```

### Notes for Backend Team

- Accept the same `audio` field name and `multipart/form-data` encoding.
- Return `risk` as one of `low`, `medium`, or `high`.
- Return `confidence` as a float between 0 and 1.
- Keep messages honest and non-diagnostic (e.g., "bukan diagnosis").
- If you need a different endpoint or field name, update both `src/lib/api.ts` and `src/app/api/analyze/route.ts`.

## Privacy & Disclosure

- Add a footer note on every page:
  > "Fitur ini adalah prototipe untuk hackathon dan bukan diagnosis medis."
- The `/transparency` page explains:
  - AI-generated or third-party assets used.
  - The 3D model source and license.
  - The platform is a prototype and not a medical diagnostic tool.
  - Users should consult healthcare professionals for any medical concerns.

## Assets & AI-Generated Content

- **All images, illustrations, icons, 3D models, and generated materials must be documented and disclosed.**
- Record the source/tool and prompt in `docs/assets.md`.
- Do not use copyrighted or unlicensed assets without clearance.

## Suggested Project Structure

```
src/
  app/
    layout.tsx
    page.tsx
    analyze/
      page.tsx       # functional audio analysis page
    api/
      analyze/
        route.ts     # proxy + mock CNN endpoint
    transparency/
      page.tsx
    globals.css
  components/
    ui/              # shadcn/ui primitives
    Navbar.tsx       # edge-aligned minimal nav
    Hero.tsx         # stat-led hero
    LabStrip.tsx     # WHO metadata band
    Stats.tsx        # asymmetric stat cards
    Manifesto.tsx    # large typographic statement
    Statement.tsx    # manifesto band
    Workflow.tsx     # 3-step sequence + 3D model
    Science.tsx      # pull quote + marginalia
    CaseFile.tsx     # fictional patient vignette
    Faq.tsx          # native details/summary FAQ
    Footer.tsx       # dense typographic footer
    AudioSpectrum.tsx    # hand-built static waveform
    LiveWaveform.tsx     # real-time frequency visualizer
    AudioRecorder.tsx    # record/upload + analysis UI
    LungModel.tsx        # React Three Fiber scene
    LungModelWrapper.tsx # next/dynamic ssr: false wrapper
    Background.tsx       # noise + organic blob background
  lib/
    utils.ts         # cn() helper
    types.ts         # shared types including AnalysisResult
    api.ts           # client-side API helper
  hooks/
    useReducedMotion.ts
    useAudioRecorder.ts
    useAnalysis.ts
public/
  models/
    lung.glb         # 3D lung model
docs/
  assets.md          # asset disclosure log
```

## Deployment

- Default target: **Vercel**.
- Build command: `npm run build`.
- Use branch previews for pull requests.
- Do not use static export unless Vercel deployment requires it; standard Next.js output preserves App Router features.

## Rules of Thumb

- Build the smallest working version first. Polish comes after the core flow is stable.
- If a design or interaction decision conflicts with accessibility, choose accessibility.
- Keep the prototype honest: it must be obvious that results are not a medical diagnosis.
- When in doubt, refer to the official Next.js 16, React Three Fiber, and Tailwind CSS v4 documentation.
