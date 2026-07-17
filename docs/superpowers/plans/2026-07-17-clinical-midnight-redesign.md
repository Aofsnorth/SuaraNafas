# Clinical Midnight Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Track every checkbox and run the listed validation before moving forward.

**Goal:** Implement the approved Dark Clinical Midnight redesign across `/`, `/analyze`, and `/transparency` while preserving the audio API contract and making mock output explicitly non-clinical.

**Architecture:** `design.md` is the normative system; `tokens.css` is its runtime representation. Shared server-compatible primitives provide the visual language, while small client components own navigation state, pointer sheen, recording, and 3D behavior. Each task leaves the application lintable and buildable so implementation can stop safely at any checkpoint.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript strict mode, Tailwind CSS v4, Framer Motion, React Three Fiber, Drei, Three.js, `next/font`.

## Global Constraints

- Do not add dependencies.
- Do not delete routes or production component files.
- Do not change `POST /api/analyze`, multipart field `audio`, `AnalysisResult`, or backend forwarding behavior.
- Mock mode must use neutral `Skenario simulasi A/B/C` labels and must say that audio was not analysed.
- User-facing copy stays in Bahasa Indonesia; identifiers and file names stay in English and kebab-case.
- Server Components remain the default; add client boundaries only for browser state or interaction.
- Interactive targets are at least 44 × 44 CSS px.
- Test responsive behavior at 320, 375, 414, 768, 960, and 1440 px.
- Respect `prefers-reduced-motion`.
- Do not commit or create a branch unless the user explicitly requests it.
- After each task, run `npm run lint`; run `npm run build` at the checkpoints named below.

---

## File Structure

### New files

- `src/components/convex-surface.tsx` — server-compatible visual surface primitive.
- `src/components/convex-sheen.tsx` — optional client-only pointer sheen.
- `src/components/breathing-headline.tsx` — server-rendered accessible hero headline.
- `src/components/tb-data-section.tsx` — server-rendered verified WHO data section.
- `src/lib/tb-data.ts` — typed WHO data and source URLs.

### Core modified files

- `tokens.css` — canonical runtime colour, spacing, type, radius, and motion tokens.
- `src/app/globals.css` — Tailwind mapping, surface CSS, navbar, background, page layouts, responsive and reduced-motion rules.
- `src/components/Navbar.tsx` — responsive three-zone navigation and full-width mobile dialog.
- `src/components/AtmosphericBackground.tsx` — static acoustic layers with one animated waveform.
- `src/components/Background.tsx` — route-specific background wrapper.
- `src/components/Hero.tsx` — approved non-stat hero.
- `src/components/LabStrip.tsx` — contextual prototype/status strip.
- `src/components/Manifesto.tsx` — open why-sound narrative.
- `src/components/Workflow.tsx` — three-step workflow plus lazy 3D specimen.
- `src/components/Science.tsx` — sourced product-science explanation without an unsupported quotation.
- `src/components/CaseFile.tsx` — explicitly fictional scenario.
- `src/components/Faq.tsx` — honest privacy, demo, diagnosis, and accuracy answers.
- `src/components/Statement.tsx` — final CTA section.
- `src/components/Landing.tsx` — Signal Narrative composition.
- `src/components/AudioRecorder.tsx` — Workbench UI and neutral mock rendering.
- `src/components/LungModel.tsx` — ice-blue material and reduced-motion behavior.
- `src/components/LungModelWrapper.tsx` — intersection-based rendering, WebGL check, and fallback.
- `src/components/Footer.tsx` — statement footer and compact colophon.
- `src/app/analyze/page.tsx` — app background variant.
- `src/app/transparency/page.tsx` — Long Document disclosure page.
- `src/app/api/analyze/route.ts` — non-clinical mock copy only.

### Compatibility and integrity files

- `src/components/AsciiHero.tsx` — compatibility wrapper for `BreathingHeadline`; remove interval animation.
- `src/components/GlassCard.tsx` — compatibility wrapper for `ConvexSurface`; remove hover lift.
- `src/components/Bento.tsx` — remove stale clinical mock language or delegate to approved components.
- `src/components/Stats.tsx` — consume `TB_DATA` rather than local ambiguous metrics.
- `docs/assets.md` — keep disclosures current.
- `.hallmark/log.json` — prepend the approved app-level design entry.

---

### Task 1: Establish a clean baseline and canonical runtime tokens

**Files:**
- Modify: `tokens.css`
- Modify: `src/app/globals.css`

**Interfaces:**
- Produces CSS variables consumed by every later task.
- `--color-control-border` is reserved for meaningful UI boundaries.
- `--color-rule` and `--color-rule-2` remain decorative.

- [ ] **Step 1: Record the baseline**

Run:

```bash
npm run lint
npm run build
```

Expected:

- Both commands exit with code `0`.
- If either fails before changes, record the exact existing error and stop. Do not mix baseline repair into the redesign without user approval.

- [ ] **Step 2: Replace the `tokens.css` root block with the approved canonical values**

Use this complete runtime token set:

```css
:root {
  --color-paper: oklch(11% 0.022 250);
  --color-paper-2: oklch(15% 0.028 250);
  --color-paper-3: oklch(20% 0.035 250);
  --color-ink: oklch(95% 0.012 235);
  --color-ink-2: oklch(76% 0.025 240);
  --color-rule: oklch(30% 0.035 245);
  --color-rule-2: oklch(38% 0.045 245);
  --color-control-border: oklch(60% 0.055 230);
  --color-neutral: oklch(48% 0.032 242);
  --color-muted: oklch(62% 0.035 240);
  --color-accent: oklch(79% 0.16 220);
  --color-accent-2: oklch(72% 0.11 238);
  --color-accent-ink: oklch(12% 0.025 250);
  --color-focus: oklch(85% 0.19 215);
  --color-error: oklch(66% 0.19 25);
  --color-warning: oklch(79% 0.13 82);
  --color-success: oklch(73% 0.12 158);

  --background: var(--color-paper);
  --foreground: var(--color-ink);
  --card: var(--color-paper-2);
  --card-foreground: var(--color-ink);
  --popover: var(--color-paper-2);
  --popover-foreground: var(--color-ink);
  --primary: var(--color-accent);
  --primary-foreground: var(--color-accent-ink);
  --secondary: var(--color-paper-3);
  --secondary-foreground: var(--color-ink);
  --muted: var(--color-paper-3);
  --muted-foreground: var(--color-muted);
  --accent: var(--color-accent);
  --accent-foreground: var(--color-accent-ink);
  --destructive: var(--color-error);
  --destructive-foreground: var(--color-paper);
  --border: var(--color-rule);
  --input: var(--color-control-border);
  --ring: var(--color-focus);

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

  --radius: 0.75rem;
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

- [ ] **Step 3: Update Tailwind mappings in `globals.css`**

Add these mappings inside `@theme inline`:

```css
--color-control-border: var(--color-control-border);
--color-error: var(--color-error);
--color-warning: var(--color-warning);
--color-success: var(--color-success);
--radius-panel: var(--radius-panel);
--radius-control: var(--radius-control);
```

Update the Hallmark header comment so it names:

```css
/* Hallmark · genre: technical-atmospheric · design-system: design.md
 * marketing: Marquee Hero → Signal Narrative · app: Workbench · content: Long Document
 * theme: custom · axes: dark / roman-serif / cool-cyan
 * nav: gallery-inspired compact · footer: statement · enrichment: acoustic signal field + lazy 3D specimen
 */
```

- [ ] **Step 4: Keep base CSS stable**

Confirm these rules remain present:

```css
html,
body {
  overflow-x: clip;
}

body {
  min-height: 100%;
  background: var(--color-paper);
  color: var(--color-ink);
}

:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
```

- [ ] **Step 5: Validate Task 1**

Run:

```bash
npm run lint
npm run build
```

Expected: both commands exit `0`.

**Rollback:** restore `tokens.css` and the `@theme inline` additions. No component depends on these tokens before Task 2.

---

### Task 2: Add reusable convex surface primitives

**Files:**
- Create: `src/components/convex-surface.tsx`
- Create: `src/components/convex-sheen.tsx`
- Modify: `src/app/globals.css`
- Modify: `src/components/GlassCard.tsx`

**Interfaces:**
- Produces `ConvexSurface` and `ConvexSheen` for Tasks 5–9.
- `ConvexSurface` is server-compatible.
- `ConvexSheen` is an optional client wrapper.

- [ ] **Step 1: Create the server-compatible surface primitive**

Write `src/components/convex-surface.tsx`:

```tsx
import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ConvexSurfaceVariant = "panel" | "card" | "note";
export type ConvexSurfaceElement = "article" | "aside" | "div" | "section";

interface ConvexSurfaceProps extends HTMLAttributes<HTMLElement> {
  as?: ConvexSurfaceElement;
  children: ReactNode;
  variant?: ConvexSurfaceVariant;
}

export function ConvexSurface({
  as = "div",
  children,
  className,
  variant = "card",
  ...props
}: ConvexSurfaceProps) {
  const classes = cn("convex-surface", `convex-surface--${variant}`, className);

  if (as === "article") {
    return <article className={classes} {...props}>{children}</article>;
  }

  if (as === "aside") {
    return <aside className={classes} {...props}>{children}</aside>;
  }

  if (as === "section") {
    return <section className={classes} {...props}>{children}</section>;
  }

  return <div className={classes} {...props}>{children}</div>;
}
```

- [ ] **Step 2: Create the client-only sheen wrapper**

Write `src/components/convex-sheen.tsx`:

```tsx
"use client";

import { useEffect, useRef, type PointerEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ConvexSheenProps {
  children: ReactNode;
  className?: string;
}

export function ConvexSheen({ children, className }: ConvexSheenProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);

  const updatePosition = (event: PointerEvent<HTMLDivElement>) => {
    const root = rootRef.current;
    if (!root || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      return;
    }

    const rect = root.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;

    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
    }

    frameRef.current = window.requestAnimationFrame(() => {
      root.style.setProperty("--sheen-x", `${x}%`);
      root.style.setProperty("--sheen-y", `${y}%`);
      root.dataset.active = "true";
    });
  };

  const resetPosition = () => {
    const root = rootRef.current;
    if (!root) return;
    root.dataset.active = "false";
  };

  useEffect(() => {
    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className={cn("convex-sheen", className)}
      onPointerMove={updatePosition}
      onPointerLeave={resetPosition}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Add surface CSS**

Add to `globals.css` inside `@layer components`:

```css
.convex-surface {
  position: relative;
  min-width: 0;
  overflow: hidden;
  isolation: isolate;
  color: var(--color-ink);
  border: 1px solid color-mix(in oklch, var(--color-control-border) 72%, transparent);
  background:
    linear-gradient(145deg, color-mix(in oklch, var(--color-ink) 8%, transparent), transparent 28%),
    color-mix(in oklch, var(--color-paper-2) 82%, transparent);
  box-shadow:
    inset 1px 1px 0 color-mix(in oklch, var(--color-ink) 16%, transparent),
    inset -18px -22px 42px color-mix(in oklch, var(--color-paper) 52%, transparent),
    0 22px 60px color-mix(in oklch, var(--color-paper) 72%, transparent);
  backdrop-filter: blur(24px) saturate(132%);
  -webkit-backdrop-filter: blur(24px) saturate(132%);
}

.convex-surface::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(
    150deg,
    color-mix(in oklch, var(--color-ink) 8%, transparent),
    transparent 34%,
    color-mix(in oklch, var(--color-accent) 5%, transparent)
  );
}

.convex-surface--panel {
  border-radius: var(--radius-panel);
  background:
    linear-gradient(145deg, color-mix(in oklch, var(--color-ink) 10%, transparent), transparent 26%),
    color-mix(in oklch, var(--color-paper-2) 88%, transparent);
  box-shadow:
    inset 1px 1px 0 color-mix(in oklch, var(--color-ink) 19%, transparent),
    inset -24px -30px 64px color-mix(in oklch, var(--color-paper) 58%, transparent),
    0 28px 80px color-mix(in oklch, var(--color-paper) 78%, transparent);
}

.convex-surface--card {
  border-radius: var(--radius-card-a);
}

.convex-surface--note {
  border-radius: 0.75rem 0.25rem 0.75rem 0.375rem;
  background: color-mix(in oklch, var(--color-paper-2) 92%, transparent);
  box-shadow: inset 1px 1px 0 color-mix(in oklch, var(--color-ink) 10%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.convex-sheen {
  --sheen-x: 50%;
  --sheen-y: 20%;
  position: relative;
  min-width: 0;
}

.convex-sheen::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 3;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
  background: radial-gradient(
    circle at var(--sheen-x) var(--sheen-y),
    color-mix(in oklch, var(--color-accent) 17%, transparent),
    transparent 34%
  );
  transition: opacity var(--dur-short) var(--ease-out);
}

@media (hover: hover) and (pointer: fine) {
  .convex-sheen[data-active="true"]::after {
    opacity: 1;
  }
}

@media (max-width: 40rem) {
  .convex-surface {
    background: color-mix(in oklch, var(--color-paper-2) 94%, transparent);
    backdrop-filter: blur(14px) saturate(115%);
    -webkit-backdrop-filter: blur(14px) saturate(115%);
  }
}

@supports not (backdrop-filter: blur(1px)) {
  .convex-surface,
  .convex-surface--panel,
  .convex-surface--note {
    background: var(--color-paper-2);
  }
}
```

- [ ] **Step 4: Convert `GlassCard` into a compatibility wrapper**

Replace `src/components/GlassCard.tsx` with:

```tsx
import type { ReactNode } from "react";
import { ConvexSurface } from "@/components/convex-surface";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
}

export function GlassCard({ children, className }: GlassCardProps) {
  return (
    <ConvexSurface className={className} variant="card">
      {children}
    </ConvexSurface>
  );
}
```

- [ ] **Step 5: Validate Task 2**

Run:

```bash
npm run lint
npm run build
```

Expected: both commands exit `0`.

**Rollback:** remove the two new components, restore `GlassCard.tsx`, and remove the convex CSS block.

---

### Task 3: Centralize verified WHO data and neutralize mock API copy

**Files:**
- Create: `src/lib/tb-data.ts`
- Create: `src/components/tb-data-section.tsx`
- Modify: `src/app/api/analyze/route.ts`
- Modify: `src/components/Stats.tsx`

**Interfaces:**
- Produces `TbDatum` and `TB_DATA` for landing and compatibility components.
- Preserves the existing `AnalysisResult` shape.

- [ ] **Step 1: Create typed data constants**

Write `src/lib/tb-data.ts`:

```ts
export interface TbDatum {
  value: string;
  label: string;
  definition: string;
  year: number;
  sourceTitle: string;
  sourceUrl: string;
  note?: string;
}

export const TB_DATA: readonly TbDatum[] = [
  {
    value: "10,8 juta",
    label: "Estimasi orang yang jatuh sakit akibat TB secara global",
    definition: "Estimasi kasus insiden TB, bukan jumlah diagnosis yang dilaporkan.",
    year: 2023,
    sourceTitle: "WHO Global Tuberculosis Report 2024 — TB incidence",
    sourceUrl:
      "https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-disease-burden/1-1-tb-incidence",
    note: "Interval ketidakpastian 10,1–11,7 juta; 134 kasus insiden per 100.000 penduduk.",
  },
  {
    value: "8,2 juta",
    label: "Orang dengan episode TB baru atau kambuh yang didiagnosis dan dinotifikasi",
    definition: "Kasus baru dan kambuh yang didiagnosis dan dinotifikasi, bukan estimasi total insiden.",
    year: 2023,
    sourceTitle: "WHO Global Tuberculosis Report 2024 — Case notifications",
    sourceUrl:
      "https://www.who.int/teams/global-programme-on-tuberculosis-and-lung-health/tb-reports/global-tuberculosis-report-2024/tb-diagnosis-and-treatment/2-1-case-notifications",
  },
  {
    value: "10%",
    label: "Perkiraan bagian Indonesia dari kasus insiden TB global",
    definition: "Proporsi estimasi kasus insiden TB global yang dikaitkan WHO dengan Indonesia.",
    year: 2023,
    sourceTitle: "WHO — Tuberculosis resurges as top infectious disease killer",
    sourceUrl:
      "https://www.who.int/news/item/29-10-2024-tuberculosis-resurges-as-top-infectious-disease-killer",
  },
] as const;
```

- [ ] **Step 2: Create the WHO data section**

Write `src/components/tb-data-section.tsx`:

```tsx
import Link from "next/link";
import { ConvexSurface } from "@/components/convex-surface";
import { TB_DATA } from "@/lib/tb-data";

export function TbDataSection() {
  return (
    <section id="sains" className="landing-section scroll-mt-28" aria-labelledby="tb-data-title">
      <div className="section-shell">
        <header className="section-heading">
          <p className="section-tag">Data terverifikasi</p>
          <h2 id="tb-data-title">Angka selalu datang bersama konteksnya.</h2>
          <p>
            Estimasi insiden, laporan diagnosis, dan bagian Indonesia mengukur hal
            yang berbeda. Tahun dan definisinya tetap terlihat di setiap kartu.
          </p>
        </header>

        <div className="tb-data-grid">
          {TB_DATA.map((datum, index) => (
            <ConvexSurface
              as="article"
              className={`tb-data-card tb-data-card--${index + 1}`}
              key={datum.label}
              variant="card"
            >
              <p className="tb-data-card__year">WHO · {datum.year}</p>
              <p className="tb-data-card__value">{datum.value}</p>
              <h3>{datum.label}</h3>
              <p>{datum.definition}</p>
              {datum.note ? <p className="tb-data-card__note">{datum.note}</p> : null}
              <Link href={datum.sourceUrl} target="_blank" rel="noreferrer">
                {datum.sourceTitle} ↗
              </Link>
            </ConvexSurface>
          ))}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Replace mock route messages without changing the contract**

In `src/app/api/analyze/route.ts`, replace mock message maps with:

```ts
const MOCK_MESSAGE =
  "Simulasi antarmuka. Audio yang dikirim tidak dianalisis untuk pola TB.";

const MOCK_RECOMMENDATION =
  "Hubungkan backend tervalidasi untuk memperoleh output model. Untuk kekhawatiran kesehatan, konsultasikan ke tenaga medis.";
```

Update `buildMockResult` to return:

```ts
return {
  risk,
  confidence: Number(confidence.toFixed(2)),
  message: MOCK_MESSAGE,
  recommendation: MOCK_RECOMMENDATION,
  source: "mock",
};
```

Do not change the backend branch.

- [ ] **Step 4: Convert legacy `Stats` to the same data source**

Replace `src/components/Stats.tsx` with this compatibility wrapper so all callers use the verified section:

```tsx
import { TbDataSection } from "@/components/tb-data-section";

export function Stats() {
  return <TbDataSection />;
}
```

Do not keep the ambiguous `2,7 juta kasus tidak terlapor` card.

- [ ] **Step 5: Validate Task 3**

Run:

```bash
npm run lint
npm run build
```

Expected: both commands exit `0`; the route type remains `AnalysisResult`.

**Rollback:** restore the previous mock copy and `Stats`; the new data files can be removed without affecting existing routes until Task 6.

---

### Task 4: Implement the responsive gallery-inspired navbar

**Files:**
- Modify: `src/components/Navbar.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- Produces shared navigation for all routes.
- Section links are always `/#cara-kerja`, `/#sains`, and `/#faq`.
- CTA is `/analyze`, except on `/analyze`, where it becomes `Beranda` → `/`.

- [ ] **Step 1: Replace `Navbar.tsx` with an accessible client implementation**

Use this structure:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent } from "react";

const NAV_LINKS = [
  { href: "/#cara-kerja", label: "Cara kerja" },
  { href: "/#sains", label: "Sains" },
  { href: "/#faq", label: "FAQ" },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const isAnalyzePage = pathname === "/analyze";
  const actionHref = isAnalyzePage ? "/" : "/analyze";
  const actionLabel = isAnalyzePage ? "Beranda" : "Mulai deteksi";
  const mobileActionLabel = isAnalyzePage ? "Beranda" : "Mulai";

  useEffect(() => {
    const sentinel = document.querySelector("[data-nav-sentinel]");
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => setIsScrolled(!entry.isIntersecting),
      { threshold: 0 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  const openMenu = () => {
    dialogRef.current?.showModal();
    setIsMenuOpen(true);
  };

  const closeMenu = () => {
    dialogRef.current?.close();
  };

  const handleDialogClose = () => {
    setIsMenuOpen(false);
    triggerRef.current?.focus();
  };

  const handleBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === dialogRef.current) closeMenu();
  };

  return (
    <>
      <span data-nav-sentinel className="nav-sentinel" aria-hidden="true" />
      <header className="site-header" data-scrolled={isScrolled ? "true" : "false"}>
        <nav className="site-nav" aria-label="Navigasi utama">
          <Link className="site-nav__wordmark" href="/" aria-label="Beranda GarudaHacks TB">
            <span className="site-nav__wordmark-label site-nav__wordmark-label--desktop">
              GARUDAHACKS / TB
            </span>
            <span className="site-nav__wordmark-label site-nav__wordmark-label--mobile">
              GH / TB
            </span>
          </Link>

          <div className="site-nav__links">
            {NAV_LINKS.map((link) => (
              <Link href={link.href} key={link.href}>
                {link.label}
              </Link>
            ))}
          </div>

          <div className="site-nav__actions">
            <Link className="site-nav__cta" href={actionHref}>
              <span className="site-nav__cta-label site-nav__cta-label--desktop">
                {actionLabel}
              </span>
              <span className="site-nav__cta-label site-nav__cta-label--mobile">
                {mobileActionLabel}
              </span>
            </Link>
            <button
              ref={triggerRef}
              type="button"
              className="site-nav__menu-trigger"
              aria-controls="mobile-navigation"
              aria-expanded={isMenuOpen}
              aria-label="Buka menu navigasi"
              onClick={openMenu}
            >
              Menu
            </button>
          </div>
        </nav>
      </header>

      <dialog
        ref={dialogRef}
        id="mobile-navigation"
        className="mobile-navigation"
        onClick={handleBackdropClick}
        onClose={handleDialogClose}
      >
        <div className="mobile-navigation__panel">
          <div className="mobile-navigation__topline">
            <span>GARUDAHACKS / TB</span>
            <button type="button" onClick={closeMenu} aria-label="Tutup menu navigasi">
              Tutup
            </button>
          </div>
          <div className="mobile-navigation__links">
            {NAV_LINKS.map((link) => (
              <Link href={link.href} key={link.href} onClick={closeMenu}>
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </dialog>
    </>
  );
}
```

- [ ] **Step 2: Add navbar CSS**

Implement these invariants:

```css
.nav-sentinel {
  position: absolute;
  inset-block-start: 0;
  inset-inline-start: 0;
  width: 1px;
  height: 1px;
}

.site-header {
  position: fixed;
  inset: 0 0 auto;
  z-index: var(--z-sticky);
  border-bottom: 1px solid transparent;
  background: color-mix(in oklch, var(--color-paper) 66%, transparent);
  transition:
    background-color var(--dur-short) var(--ease-out),
    border-color var(--dur-short) var(--ease-out);
}

.site-header[data-scrolled="true"] {
  border-color: var(--color-rule);
  background: color-mix(in oklch, var(--color-paper) 90%, transparent);
  backdrop-filter: blur(18px) saturate(118%);
}

.site-nav {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  min-height: 4.5rem;
  padding-inline: clamp(1rem, 3vw, 2.5rem);
}

.site-nav__wordmark,
.site-nav__links a,
.site-nav__cta,
.site-nav__menu-trigger {
  white-space: nowrap;
}

.site-nav__actions {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.site-nav__cta,
.site-nav__menu-trigger {
  min-height: 44px;
  border: 1px solid var(--color-control-border);
  border-radius: var(--radius-control);
}

.site-nav__links,
.site-nav__cta-label--desktop,
.site-nav__wordmark-label--desktop {
  display: none;
}

.site-nav__menu-trigger,
.site-nav__cta-label--mobile,
.site-nav__wordmark-label--mobile {
  display: inline-flex;
}

@media (min-width: 60rem) {
  .site-nav {
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  }

  .site-nav__links {
    display: flex;
  }

  .site-nav__cta-label--desktop,
  .site-nav__wordmark-label--desktop {
    display: inline-flex;
  }

  .site-nav__menu-trigger,
  .site-nav__cta-label--mobile,
  .site-nav__wordmark-label--mobile {
    display: none;
  }
}
```

The dialog must use `position: fixed; inset: 0; width: 100%; max-width: none; margin: 0;` and a full-width panel. It must not become a floating rounded card.

- [ ] **Step 3: Validate keyboard and responsive behavior**

Run:

```bash
npm run lint
npm run build
```

Then check in a browser:

- Desktop tab order: wordmark → `Cara kerja` → `Sains` → `FAQ` → CTA; the hidden menu trigger is not focusable.
- Mobile tab order: wordmark → short CTA → menu trigger; hidden centre links are not focusable.
- At 320 px, wordmark, short CTA, and menu do not overlap or wrap.
- Escape closes the dialog.
- Backdrop click closes the dialog.
- Focus returns to the menu trigger.

**Rollback:** restore the previous `Navbar.tsx` and remove navbar/dialog CSS.

---

### Task 5: Replace the random background system and rapid hero morph

**Files:**
- Create: `src/components/breathing-headline.tsx`
- Modify: `src/app/page.tsx`
- Modify: `src/components/AtmosphericBackground.tsx`
- Modify: `src/components/Background.tsx`
- Modify: `src/components/AsciiHero.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- Produces `AtmosphericBackground({ variant })` with `landing | app | document`.
- Produces `BreathingHeadline({ id, children })`.

- [ ] **Step 1: Create the accessible breathing headline**

Write `src/components/breathing-headline.tsx`:

```tsx
import type { ReactNode } from "react";

interface BreathingHeadlineProps {
  children: ReactNode;
  className?: string;
  id: string;
}

export function BreathingHeadline({ children, className, id }: BreathingHeadlineProps) {
  return (
    <div className={className}>
      <h1 id={id} className="sr-only">{children}</h1>
      <div className="breathing-headline" aria-hidden="true">
        <span className="breathing-headline__layer breathing-headline__layer--calm">
          {children}
        </span>
        <span className="breathing-headline__layer breathing-headline__layer--soft">
          {children}
        </span>
      </div>
    </div>
  );
}
```

Add CSS:

```css
.breathing-headline {
  display: grid;
  max-width: 11ch;
  font-family: var(--font-display);
  font-size: var(--text-display);
  font-style: normal;
  line-height: 0.96;
  letter-spacing: -0.04em;
}

.breathing-headline__layer {
  grid-area: 1 / 1;
}

.breathing-headline__layer--calm {
  font-variation-settings: "SOFT" 0, "WONK" 0;
  animation: headline-calm var(--dur-breath) var(--ease-in-out) infinite;
}

.breathing-headline__layer--soft {
  font-variation-settings: "SOFT" 80, "WONK" 1;
  animation: headline-soft var(--dur-breath) var(--ease-in-out) infinite;
}

@keyframes headline-calm {
  0%, 45%, 100% { opacity: 1; }
  55%, 90% { opacity: 0; }
}

@keyframes headline-soft {
  0%, 45%, 100% { opacity: 0; }
  55%, 90% { opacity: 1; }
}
```

- [ ] **Step 2: Rewrite `AtmosphericBackground` as a static server component**

Remove hooks and generated random arrays. Use fixed SVG paths and fixed particle coordinates. The component signature is:

```tsx
export type BackgroundVariant = "landing" | "app" | "document";

interface AtmosphericBackgroundProps {
  variant?: BackgroundVariant;
}

export function AtmosphericBackground({
  variant = "landing",
}: AtmosphericBackgroundProps) {
  return (
    <div className="signal-field" data-variant={variant} aria-hidden="true">
      <div className="signal-field__glow signal-field__glow--one" />
      <div className="signal-field__glow signal-field__glow--two" />
      <div className="signal-field__noise" />
      <div className="signal-field__grid" />
      <div className="signal-field__contours" />
      <svg className="signal-field__wave" viewBox="0 0 1600 520" preserveAspectRatio="none">
        <path className="signal-field__wave-echo" d="M0 292 C120 270 190 322 310 286 S520 254 650 298 S890 332 1015 281 S1280 236 1600 294" />
        <path className="signal-field__wave-main" d="M0 270 C120 238 206 320 326 273 S526 222 654 284 S884 354 1018 265 S1298 204 1600 276" />
      </svg>
      <div className="signal-field__scan" />
      <div className="signal-field__particles" />
    </div>
  );
}
```

Use CSS-generated static particle dots; do not animate individual particles.

- [ ] **Step 3: Implement route intensity through CSS**

```css
.signal-field[data-variant="landing"] { --signal-opacity: 1; }
.signal-field[data-variant="app"] { --signal-opacity: 0.46; }
.signal-field[data-variant="document"] { --signal-opacity: 0.18; }

.signal-field[data-variant="document"] .signal-field__wave,
.signal-field[data-variant="document"] .signal-field__scan,
.signal-field[data-variant="document"] .signal-field__particles {
  display: none;
}
```

Only `.signal-field__wave-main` loops. Glows, contours, grid, echo path, and particles stay static. The scan uses a one-shot keyframe with a long idle portion.

- [ ] **Step 4: Convert `Background` and `AsciiHero` into wrappers**

Keep `src/app/page.tsx` as the landing-background owner and make the variant explicit:

```tsx
<AtmosphericBackground variant="landing" />
```

`Background.tsx` remains the route wrapper for non-landing pages:

```tsx
import {
  AtmosphericBackground,
  type BackgroundVariant,
} from "@/components/AtmosphericBackground";

interface BackgroundProps {
  variant?: Exclude<BackgroundVariant, "landing">;
}

export function Background({ variant = "app" }: BackgroundProps) {
  return <AtmosphericBackground variant={variant} />;
}
```

`AsciiHero.tsx`:

```tsx
import { BreathingHeadline } from "@/components/breathing-headline";

export function AsciiHero() {
  return (
    <BreathingHeadline id="landing-title">
      Dengarkan paru-paru berbicara.
    </BreathingHeadline>
  );
}
```

- [ ] **Step 5: Add reduced-motion rules**

```css
@media (prefers-reduced-motion: reduce) {
  .breathing-headline__layer--calm {
    animation: none;
    opacity: 1;
  }

  .breathing-headline__layer--soft,
  .signal-field__scan,
  .convex-sheen::after {
    display: none;
  }

  .signal-field__wave-main {
    animation: none;
  }
}
```

- [ ] **Step 6: Validate Task 5**

Run:

```bash
npm run lint
npm run build
```

In browser devtools, confirm the two headline layers occupy identical geometry at 320, 414, and 1440 px.

**Rollback:** restore the previous background and `AsciiHero`; remove `breathing-headline.tsx` and the new CSS.

---

### Task 6: Compose the approved Signal Narrative landing page

**Files:**
- Modify: `src/components/Hero.tsx`
- Modify: `src/components/LabStrip.tsx`
- Modify: `src/components/Manifesto.tsx`
- Modify: `src/components/Workflow.tsx`
- Modify: `src/components/Science.tsx`
- Modify: `src/components/CaseFile.tsx`
- Modify: `src/components/Faq.tsx`
- Modify: `src/components/Statement.tsx`
- Modify: `src/components/Landing.tsx`
- Modify: `src/components/Bento.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- Consumes `BreathingHeadline`, `ConvexSurface`, `TbDataSection`, and `LungModelWrapper`.
- Produces section anchors `cara-kerja`, `sains`, and `faq` used by Navbar.

- [ ] **Step 1: Replace the hero content**

`Hero.tsx` must render:

```tsx
<section className="landing-hero" aria-labelledby="landing-title">
  <div className="section-shell landing-hero__inner">
    <p className="section-tag">GarudaHacks 7.0 · prototipe skrining akustik</p>
    <BreathingHeadline id="landing-title">
      Dengarkan paru-paru berbicara.
    </BreathingHeadline>
    <p className="landing-hero__lede">
      Prototipe skrining awal yang mengubah suara batuk dan pernapasan menjadi
      representasi spektrum untuk antarmuka analisis. Hasil bukan diagnosis medis.
    </p>
    <div className="landing-hero__actions">
      <Link className="btn-primary" href="/analyze">Mulai deteksi</Link>
      <Link className="cta-link" href="#cara-kerja">Lihat cara kerja →</Link>
    </div>
  </div>
</section>
```

Do not render an epidemiology statistic in this section.

- [ ] **Step 2: Replace `LabStrip` with contextual status items**

Use exactly these four items:

```ts
const items = [
  { label: "Status", value: "Prototipe hackathon" },
  { label: "Batas", value: "Bukan diagnosis medis" },
  { label: "Data", value: "WHO · tahun + definisi" },
  { label: "Backend", value: "Mode demo jika belum terhubung" },
] as const;
```

- [ ] **Step 3: Make `Manifesto` an open narrative**

Remove the card wrapper. Use the heading:

```text
Suara membawa pola. Skrining awal membantu menentukan langkah berikutnya.
```

The body must say that the prototype explores an acoustic screening interface and still requires clinical confirmation. Do not say that the current model has detected validated TB biomarkers.

- [ ] **Step 4: Update `Workflow`**

- Use section id `cara-kerja`.
- Render three `ConvexSurface` cards: `Rekam`, `Bentuk spektrum`, `Pahami hasil`.
- Describe step 02 as interface flow, not proven diagnostic inference.
- Render `LungModelWrapper` in a separate `ConvexSurface variant="panel"` beside step 02 on desktop.
- Use `ConvexSheen` only around the 3D panel.

- [ ] **Step 5: Update `Science` without an unsupported quotation**

Use section id `sains` only if `TbDataSection` does not own it. The approved implementation should let `TbDataSection` own `sains`; give this section `aria-labelledby="science-title"` without a duplicate id.

Render an accessible heading and explanatory copy:

```tsx
<section className="landing-section" aria-labelledby="science-title">
  <div className="section-shell science-narrative">
    <h2 id="science-title">Dari suara menuju representasi frekuensi.</h2>
    <p>
      Audio dapat diubah menjadi representasi frekuensi yang dapat dibaca model.
      Pada prototipe ini, bagian tersebut masih menjadi kerangka integrasi dan
      bukan bukti validasi klinis.
    </p>
  </div>
</section>
```

- [ ] **Step 6: Make the case scenario explicitly simulated**

Replace clinical outcome language with:

```text
Skenario ini menunjukkan bagaimana antarmuka mengarahkan pengguna dari rekaman menuju anjuran pemeriksaan lanjutan. Audio, skor, dan identitas sepenuhnya fiktif; tidak ada pola medis yang dianalisis.
```

Keep the `Fiktif` label visible before the name.

- [ ] **Step 7: Rewrite FAQ answers**

Required answers:

```ts
const faqs = [
  {
    question: "Ini diagnosis medis?",
    answer:
      "Tidak. Fitur ini adalah prototipe skrining awal dan tidak menggantikan dokter, pemeriksaan dahak, tes molekuler, atau rontgen dada.",
  },
  {
    question: "Ke mana audio dikirim?",
    answer:
      "Audio dikirim ke /api/analyze. Jika backend dikonfigurasi, route tersebut dapat meneruskan file ke backend tim. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.",
  },
  {
    question: "Apa arti mode demo?",
    answer:
      "Mode demo hanya mensimulasikan tampilan hasil berdasarkan ukuran file. Audio tidak dianalisis untuk pola TB.",
  },
  {
    question: "Seberapa akurat?",
    answer:
      "Belum ada angka akurasi klinis yang dapat diklaim. Tim backend perlu menyelesaikan validasi dataset, kalibrasi, dan evaluasi klinis sebelum skor dapat ditafsirkan.",
  },
] as const;
```

- [ ] **Step 8: Convert `Statement` into the final CTA**

Use one heading and one primary CTA. Do not place another glass card around the whole section.

- [ ] **Step 9: Compose `Landing.tsx` in this exact order**

```tsx
<main className="relative">
  <Hero />
  <LabStrip />
  <Manifesto />
  <Workflow />
  <Science />
  <TbDataSection />
  <CaseFile />
  <Faq />
  <Statement />
</main>
```

- [ ] **Step 10: Remove stale Bento copy without deleting the module**

Make `Bento` delegate to the approved landing composition:

```tsx
import { Landing } from "@/components/Landing";

export function Bento() {
  return <Landing />;
}
```

- [ ] **Step 11: Validate Task 6**

Run:

```bash
npm run lint
npm run build
```

Check the section order and anchors in the browser. Confirm narrative sections are open and cards are limited to workflow, data, and 3D.

**Rollback:** restore the landing components as a group. Tasks 1–5 remain independently valid.

---

### Task 7: Rebuild the analyze workbench and neutral mock states

**Files:**
- Modify: `src/components/AudioRecorder.tsx`
- Modify: `src/app/analyze/page.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- Consumes `ConvexSurface`, `ConvexSheen`, and existing hooks.
- Preserves `useAudioRecorder`, `useAnalysis`, and `AnalysisResult`.

- [ ] **Step 1: Add neutral mock scenario labels**

Use:

```ts
const MOCK_SCENARIO_LABEL: Record<RiskLevel, string> = {
  low: "Skenario simulasi A",
  medium: "Skenario simulasi B",
  high: "Skenario simulasi C",
};

const BACKEND_RISK_LABEL: Record<RiskLevel, string> = {
  low: "Risiko rendah",
  medium: "Risiko sedang",
  high: "Risiko tinggi",
};
```

Define `const isMockResult = result?.source === "mock";`. This expression is safe while `result` is null. Inside the existing `{result && (...)}` branch, treat every non-mock result, including an older response where `source` is absent, as a backend-compatible result.

When `isMockResult`:

- Render `MOCK_SCENARIO_LABEL[result.risk]`.
- Label the percentage `Nilai simulasi`.
- Render fixed copy `Simulasi antarmuka — audio tidak dianalisis.`
- Do not render `result.message` or `result.recommendation`.

When `!isMockResult`:

- Render `BACKEND_RISK_LABEL[result.risk]`.
- Label the value `Skor model`.
- Render backend message and recommendation with the non-diagnostic disclaimer.

- [ ] **Step 2: Wrap the recorder in the strong surface hierarchy**

Add stable disclosure copy and the current status label above the return statement:

```ts
const AUDIO_TRANSMISSION_DISCLOSURE =
  "Audio dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.";

const statusLabel = isRecording
  ? "Sedang merekam"
  : isProcessing
    ? "Sedang menganalisis"
    : activeBlob
      ? "Audio siap"
      : "Siap merekam";
```

Replace the current opening surface:

```tsx
<div className="grid-card p-6 md:p-10">
```

with:

```tsx
<ConvexSheen>
  <ConvexSurface
    className="recorder-workbench"
    variant="panel"
    aria-describedby={recorderError || analysisError ? "recorder-error" : undefined}
  >
```

Replace the matching closing tag immediately before `</div></section>` with:

```tsx
  </ConvexSurface>
</ConvexSheen>
```

Replace the current recorder status paragraph with:

```tsx
<header className="recorder-workbench__status" aria-live="polite">
  <p className="section-tag">{statusLabel}</p>
  {isRecording ? (
    <p className="recorder-workbench__timer">{formatDuration(duration)}</p>
  ) : null}
</header>
```

Add `id="recorder-error"` and `role="alert"` to the existing error paragraph:

```tsx
<p id="recorder-error" role="alert" className="recorder-workbench__error">
  {recorderError || analysisError}
</p>
```

Add the disclosure inside the existing selected-audio block, directly before its action row:

```tsx
<p className="recorder-workbench__disclosure">
  {AUDIO_TRANSMISSION_DISCLOSURE}
</p>
```

Replace the processing paragraph with:

```tsx
<p role="status" aria-live="polite" className="recorder-workbench__processing">
  Mengirim audio dan menunggu respons…
</p>
```

Keep every existing record, stop, upload, use-recording, analyze, reset, error, processing, and result branch in its current logical condition. Do not collapse them into a new state machine during this visual task.

- [ ] **Step 3: Add explicit live regions**

- Status line: `aria-live="polite"`.
- Processing line: `role="status"` and `aria-live="polite"`.
- Error line: `role="alert"`.
- Associate error content with the workbench via `aria-describedby` when an error exists.

- [ ] **Step 4: Add transmission disclosure beside submit**

Render this exact copy immediately above or below `Kirim untuk analisis`:

```text
Audio dikirim ke /api/analyze dan dapat diteruskan ke backend yang dikonfigurasi. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.
```

- [ ] **Step 5: Preserve retry state**

Do not call `resetRecorder`, `resetAnalysis`, or `setSource(null)` on API error. The existing hook already retains selected audio. Define:

```ts
const analyzeLabel =
  analysisStatus === "error" ? "Coba kirim lagi" : "Kirim untuk analisis";
```

Use `{analyzeLabel}` in the existing analyze button and keep `onClick={handleAnalyze}`. The same selected blob is submitted again.

- [ ] **Step 6: Apply the app background variant**

In `src/app/analyze/page.tsx`:

```tsx
<Background variant="app" />
```

- [ ] **Step 7: Validate Task 7**

Run:

```bash
npm run lint
npm run build
```

Browser checks:

- Deny microphone permission and confirm upload remains available.
- Upload a non-empty audio file with no backend configured.
- Confirm `Mode demo`, `Skenario simulasi A/B/C`, `Nilai simulasi`, and the fixed simulation copy appear.
- Confirm no mock `Risiko tinggi/rendah/sedang` label appears.
- Trigger an API failure and confirm the selected audio remains available for retry.

**Rollback:** restore `AudioRecorder.tsx` and the analyze page. API mock copy from Task 3 remains safe.

---

### Task 8: Make the 3D specimen genuinely lazy and resilient

**Files:**
- Modify: `src/components/LungModel.tsx`
- Modify: `src/components/LungModelWrapper.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- `LungModelWrapper` renders a fixed-size loading shell until intersection.
- It renders a textual fallback when WebGL is unavailable or the scene throws.

- [ ] **Step 1: Remove unconditional preload**

Delete:

```ts
useGLTF.preload("/models/lung.glb");
```

- [ ] **Step 2: Resolve Three.js colours from CSS tokens**

Update the React import to include `useEffect`:

```ts
import { useEffect, useMemo, useRef, useState, Suspense } from "react";
```

Delete the obsolete module-level line:

```ts
const livingMaterial = createLivingMaterial();
```

Delete the entire obsolete `createLivingMaterial()` function. Keep `createNoiseTexture()`.

Then add:

```ts
function resolveCssThreeColor(token: string, fallback: string) {
  if (typeof document === "undefined") return new THREE.Color(fallback);

  const probe = document.createElement("span");
  probe.style.color = `var(${token})`;
  probe.style.position = "absolute";
  probe.style.visibility = "hidden";
  document.body.appendChild(probe);
  const resolved = getComputedStyle(probe).color;
  probe.remove();

  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context || !resolved) return new THREE.Color(fallback);

  context.fillStyle = resolved;
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  return new THREE.Color(red / 255, green / 255, blue / 255);
}
```

Replace the module-level `livingMaterial` with this hook:

```ts
function useLivingMaterial() {
  const noise = useMemo(() => createNoiseTexture(), []);
  const material = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: resolveCssThreeColor("--color-accent", "#65dcff"),
        metalness: 0.02,
        roughness: 0.42,
        roughnessMap: noise,
        bumpMap: noise,
        bumpScale: 0.01,
        transmission: 0.78,
        thickness: 1.4,
        ior: 1.38,
        clearcoat: 0.48,
        clearcoatRoughness: 0.28,
        attenuationColor: resolveCssThreeColor("--color-paper-3", "#10243a"),
        attenuationDistance: 1.1,
        emissive: resolveCssThreeColor("--color-accent-2", "#4baed7"),
        emissiveIntensity: 0.08,
        side: THREE.DoubleSide,
      }),
    [noise],
  );

  useEffect(() => {
    return () => {
      material.dispose();
      noise.dispose();
    };
  }, [material, noise]);

  return material;
}
```

Call `const material = useLivingMaterial();` inside `LungMesh`, assign that material to cloned meshes, and update emissive intensity on this instance rather than a module-global singleton. Change the cloned-scene memo dependency list from `[scene]` to `[material, scene]`.

- [ ] **Step 3: Replace hover scale and green lights**

- Remove hover scale from the mesh.
- Keep pointer interaction on hotspots only.
- Use resolved cyan/ice-blue material and cool neutral lights.
- Reduced motion sets `autoRotate={false}` and fixes emissive intensity.

- [ ] **Step 4: Implement intersection and WebGL gates in `LungModelWrapper`**

Replace the file header with a client directive and required imports:

```tsx
"use client";

import dynamic from "next/dynamic";
import {
  Component,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
```

Then define the fallback component at module scope:

```tsx
function LungFallback() {
  return (
    <div className="lung-fallback" role="status">
      <p>
        Visualisasi 3D tidak tersedia pada perangkat ini. Alur tetap sama:
        rekam audio, bentuk representasi spektrum, lalu tampilkan hasil skrining
        atau simulasi antarmuka.
      </p>
    </div>
  );
}
```

Add a local Error Boundary below `LungFallback`:

```tsx
interface SceneErrorBoundaryProps {
  children: ReactNode;
}

interface SceneErrorBoundaryState {
  hasError: boolean;
}

class SceneErrorBoundary extends Component<
  SceneErrorBoundaryProps,
  SceneErrorBoundaryState
> {
  state: SceneErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): SceneErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) return <LungFallback />;
    return this.props.children;
  }
}
```

`componentDidCatch` stays empty because the project has no logging adapter and must not use production `console.log`.

Use this complete `LungModelWrapper` implementation around the existing dynamic import:

```tsx
export function LungModelWrapper() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [shouldRender, setShouldRender] = useState(false);
  const [canUseWebGl, setCanUseWebGl] = useState<boolean | null>(null);

  useEffect(() => {
    const canvas = document.createElement("canvas");
    const context =
      canvas.getContext("webgl2") ??
      canvas.getContext("webgl") ??
      canvas.getContext("experimental-webgl");
    setCanUseWebGl(Boolean(context));
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setShouldRender(true);
        observer.disconnect();
      },
      { rootMargin: "320px" },
    );

    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  let content: ReactNode = (
    <div className="lung-loading" role="status">
      Memuat visualisasi saat bagian ini mendekati layar…
    </div>
  );

  if (canUseWebGl === false) {
    content = <LungFallback />;
  } else if (canUseWebGl === true && shouldRender) {
    content = (
      <SceneErrorBoundary>
        <LungModel />
      </SceneErrorBoundary>
    );
  }

  return (
    <div ref={rootRef} className="lung-model-shell">
      {content}
    </div>
  );
}
```

Imports must include `useEffect`, `useRef`, `useState`, and `type ReactNode`. Keep the existing `dynamic(() => import("./LungModel"), { ssr: false })` declaration at module scope.

Fallback copy:

```text
Visualisasi 3D tidak tersedia pada perangkat ini. Alur tetap sama: rekam audio, bentuk representasi spektrum, lalu tampilkan hasil skrining atau simulasi antarmuka.
```

- [ ] **Step 5: Validate Task 8**

Run:

```bash
npm run lint
npm run build
```

Browser checks:

- Reload at the top of `/` and confirm the GLB request does not start before the workflow approaches the viewport.
- Scroll toward the specimen and confirm the request starts.
- Enable reduced motion and confirm no auto-rotation or emissive pulse.
- Disable WebGL in browser settings or force the detection branch and confirm the fallback preserves layout height.

**Rollback:** restore both 3D files. Landing remains functional because the wrapper has a stable placement.

---

### Task 9: Finish transparency, footer, compatibility copy, and project records

**Files:**
- Modify: `src/app/transparency/page.tsx`
- Modify: `src/components/Footer.tsx`
- Modify: `src/components/Stats.tsx`
- Modify: `src/components/Science.tsx`
- Modify: `docs/assets.md`
- Modify: `.hallmark/log.json`

**Interfaces:**
- Transparency is the canonical disclosure surface.
- Footer links to `/transparency` and named WHO sources.

- [ ] **Step 1: Rewrite transparency as a Long Document**

Use these sections and headings:

```text
Transparansi
Status prototipe
Alur audio
Mode demo dan backend
Data WHO
Aset dan lisensi
Batas medis
```

The `Alur audio` section must state:

```text
Browser mengirim file ke /api/analyze. Tanpa BACKEND_API_URL, route mengembalikan simulasi UI deterministik berdasarkan ukuran file. Dengan BACKEND_API_URL, route dapat meneruskan file ke endpoint /predict milik backend tim. Prototipe ini belum menjamin pemrosesan lokal atau penghapusan otomatis.
```

Use `Background variant="document"` and only one `ConvexSurface variant="note"` for the primary disclaimer.

- [ ] **Step 2: Rewrite the footer as a statement close**

Required content:

```text
Satu sinyal awal bukan diagnosis. Gunakan hasil untuk memahami langkah berikutnya, lalu konfirmasi dengan tenaga medis.
```

Below it, include:

- Team names: `Aidan Pitra Habibie` and `Muhammad Rizal Anditama`.
- WHO source links from `TB_DATA`.
- 3D attribution: `Human Reference Atlas 3D Reference Object Library / NIH Visible Human Male, CC-BY 4.0`.
- `/transparency` link.
- Hackathon prototype disclaimer.

- [ ] **Step 3: Confirm legacy components no longer contain unsafe claims**

Use FFF repository search for each phrase because the current repository may contain untracked files:

```text
fff_grep(query="diproses secara lokal", maxResults=50, output_mode="content")
fff_grep(query="dihapus setelah analisis", maxResults=50, output_mode="content")
fff_grep(query="tidak ada rekaman suara yang disimpan", maxResults=50, output_mode="content")
fff_grep(query="pola yang mencurigakan", maxResults=50, output_mode="content")
fff_grep(query="2,7 juta kasus tidak terlapor", maxResults=50, output_mode="content")
fff_grep(query="The Lancet Digital Health", maxResults=50, output_mode="content")
```

Expected: no production UI copy matches these claims.

Update `Stats.tsx` and `Science.tsx` if the search finds them. Do not delete files.

- [ ] **Step 4: Confirm asset disclosure**

Keep these entries in `docs/assets.md`:

```markdown
| `assets/chatgpt-image/image.png` | Unknown legacy source; exact tool/model not recorded | Prompt metadata was not recorded. Retained as an unused design exploration and not rendered in production. | Not used |
```

```markdown
- **Navbar Design Reference**: `assets/navbar-galery/desktop.webp`, supplied by the user as a public inspiration reference. The implementation extracts only layout DNA; it does not ship or reproduce the reference image.
```

- [ ] **Step 5: Update Hallmark history**

Prepend this object to `.hallmark/log.json` and keep the file valid JSON:

```json
{
  "date": "2026-07-17",
  "scope": "app",
  "macrostructure": "Marquee Hero → Signal Narrative / Workbench / Long Document",
  "theme": "custom",
  "theme_axes": "dark / roman-serif / cool-cyan",
  "vibe": "dark clinical midnight, acoustic signal field, restrained optical glass",
  "enrichment": "Tier-B acoustic signal field + lazy 3D specimen",
  "brief": "GarudaHacks TB multi-page clinical midnight redesign"
}
```

- [ ] **Step 6: Validate Task 9**

Run:

```bash
npm run lint
npm run build
git diff --check
```

Expected: all commands exit `0`.

**Rollback:** restore transparency/footer/legacy copy and remove the newest Hallmark entry. Tasks 1–8 remain valid.

---

### Task 10: Run full browser, accessibility, performance, and integrity validation

**Files:**
- Inspect all modified files.
- Update only files implicated by a failed check.

**Interfaces:**
- Proves the acceptance criteria in the approved spec.

- [ ] **Step 1: Run static verification**

```bash
npm run lint
npm run build
git diff --check
```

Expected: all commands exit `0`; lint reports no warnings or errors.

- [ ] **Step 2: Run integrity searches**

Use FFF repository search:

```text
fff_grep(query="mock risk prediction", maxResults=50, output_mode="content")
fff_grep(query="Risiko rendah", maxResults=50, output_mode="content")
fff_grep(query="Risiko sedang", maxResults=50, output_mode="content")
fff_grep(query="Risiko tinggi", maxResults=50, output_mode="content")
fff_grep(query="pemrosesan lokal", maxResults=50, output_mode="content")
fff_grep(query="penghapusan otomatis", maxResults=50, output_mode="content")
```

Expected:

- Backend-only risk labels may exist in `AudioRecorder.tsx` inside the non-mock branch.
- No mock-mode or project-description copy calls the result a risk prediction.
- Local-processing and deletion phrases only appear in honest statements saying the prototype does not guarantee them.

- [ ] **Step 3: Start the app in a separate terminal**

```bash
npm run dev
```

Expected: Next.js reports the local URL and no compile errors.

- [ ] **Step 4: Validate desktop landing at 1440 and 960 px**

Check:

- Three-zone navbar alignment.
- Hero contains no giant statistic.
- Background reads as one acoustic system.
- Open narrative sections are not wrapped in glass.
- Workflow, data, and 3D surfaces use the approved hierarchy.
- `Cara kerja`, `Sains`, and `FAQ` links land below the fixed header.
- GLB request begins near the workflow, not at initial page load.

- [ ] **Step 5: Validate mobile at 320, 375, 414, and 768 px**

Check:

- No horizontal scroll.
- Wordmark, short CTA, and menu fit on one line.
- No button or navigation label wraps.
- Full-width dialog opens, closes, and restores focus.
- Cards stack in information order.
- 3D loading shell and fallback retain stable height.
- Touch targets measure at least 44 px.

- [ ] **Step 6: Validate keyboard and focus**

Keyboard-only flow:

1. Navigate navbar links and CTA.
2. Open and close mobile dialog.
3. Start recording or focus upload.
4. Select audio and submit.
5. Navigate result reset/retry.
6. Open FAQ entries.
7. Focus 3D hotspots when available.

Expected: visible focus ring on every control and no focus trap leak.

- [ ] **Step 7: Validate reduced motion**

Enable `prefers-reduced-motion: reduce` and confirm:

- Headline is static.
- Waveform loop stops.
- Scan beam is absent.
- Pointer sheen is absent.
- 3D auto-rotate and emissive pulse stop.
- Functional loading feedback remains visible.

- [ ] **Step 8: Validate analyze states**

Check:

- Microphone denied.
- Recording active.
- Recording stopped.
- Uploaded file ready.
- Processing.
- API error and retry.
- Mock result.
- Backend result if a configured backend is available.

Expected for mock mode:

- Permanent `Mode demo` badge.
- Neutral `Skenario simulasi A/B/C` label.
- `Nilai simulasi` percentage label.
- Fixed statement that audio was not analysed.
- No `Risiko rendah`, `Risiko sedang`, or `Risiko tinggi` text.

Expected for backend mode:

- `Skor model` label.
- Backend message and recommendation.
- Visible non-diagnostic disclaimer.

- [ ] **Step 9: Validate transparency and footer**

Check:

- Transparency uses the document background and open reading layout.
- Audio flow names `/api/analyze`, optional forwarding, and the absence of local-processing/deletion guarantees.
- Asset and WHO source links are keyboard accessible.
- Footer statement, team credits, 3D attribution, transparency link, and disclaimer are visible on all routes.

- [ ] **Step 10: Validate network and performance behavior**

Using browser Network and Performance panels:

- Confirm `/models/lung.glb` is not requested at initial landing load.
- Confirm it is requested when the specimen approaches within the 320 px root margin.
- Confirm no scroll event listener drives the background.
- Confirm no repeated React state updates occur during pointer movement over convex surfaces.
- Confirm the hero has no layout shift when headline layers crossfade.

- [ ] **Step 11: Run the acceptance checklist against the approved spec**

Confirm every item:

- Navbar uses the three-anchor composition.
- Landing order is hero, context strip, open narrative, workflow + specimen, WHO data, case note, FAQ, CTA, footer.
- Convex surfaces follow panel/card/note hierarchy.
- Mock mode cannot be mistaken for a clinical prediction.
- No local-only processing or automatic deletion claim exists.
- WHO cards show metric, year, definition, and source together.
- Analyze and transparency use lower background intensity than landing.
- No route or production component file was deleted.

- [ ] **Step 12: Final static verification**

Stop the dev server, then run:

```bash
npm run lint
npm run build
git diff --check
git --no-pager diff --stat
git --no-optional-locks status --short
```

Expected:

- Lint and build exit `0`.
- `git diff --check` reports no whitespace errors.
- The diff contains only approved redesign, disclosure, and Hallmark-history files.
- No commit is created unless the user explicitly asks.

---

## Launch prerequisite outside this implementation

Before production launch, the backend team must publish and test:

- Accepted audio MIME types.
- Maximum upload bytes.
- Maximum recording duration.
- Rejection status codes and messages.
- Retention and deletion policy.

This redesign must not invent those limits. Track them in the backend API contract and add boundary tests when the values are agreed.

## Plan Self-Review

- Spec coverage: all approved sections map to Tasks 1–10.
- Type consistency: `BackgroundVariant`, `ConvexSurfaceVariant`, `TbDatum`, and mock/backend label maps have one definition each.
- Client boundaries: Navbar, ConvexSheen, AudioRecorder, LungModel, and LungModelWrapper are client-side; data, landing copy, surfaces, and transparency remain server-compatible.
- Content integrity: mock output, privacy wording, WHO definitions, and fictional case copy have explicit implementation steps.
- No dependencies, route deletions, API contract changes, or automatic commits are planned.

## Execution Handoff

The implementation should use one of these workflows:

1. **Subagent-Driven (recommended):** dispatch a fresh subagent per task, verify the diff and commands after each task, then run a fresh-context review before continuing.
2. **Inline Execution:** execute Tasks 1–10 in this session using `executing-plans`, stopping at each build checkpoint for review.

Do not mix the workflows within a task.
