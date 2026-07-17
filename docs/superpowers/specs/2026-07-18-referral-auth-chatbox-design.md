# Referral, Auth & AI Chatbox — Design

**Status:** Approved design
**Date:** 2026-07-18
**Scope:** `/analyze` post-detection flow, `/masuk`, `/rujukan`, and shared new layers (models, services, hooks, overlays).

## Summary

After a high-risk screening scenario on `/analyze`, the user is offered a doctor-referral flow. The flow is honesty-preserving (everything reads as `Skenario simulasi` / `Nilai simulasi`, "bukan diagnosis") and backend-ready (additive schema, so wiring the real CNN later flips it to genuine output with no redesign). Auth is required only to make a referral. All new UI reuses the Clinical Midnight primitives (`ConvexSurface`, tokens, native `<dialog>`).

## Flow (state machine)

Trigger: result is the high-risk scenario (mock high `Skenario simulasi C`, or backend high score later). Consistent dismiss label everywhere: **"Tutup"**.

```
/analyze -> scan (anonymous) -> high-risk result
  -> [ReferralPrompt]  (Tutup | Rujuk | Detail hasil)
       Tutup        -> close, stay on result
       Rujuk        -> /masuk?next=/rujukan -> (login) -> /rujukan (doctors + refer)
       Detail hasil -> [ResultDetail]  (Tutup | Analisis dengan AI)
              Tutup            -> back to ReferralPrompt
              Analisis dengan AI -> [AssistantChat popup]
```

## Architecture (MVC-like)

- **Models** (`src/models/`, plus extended `src/lib/types.ts`): pure types.
  - `AnalysisResult.detail?` (optional, additive): `scores[]`, `spectrogram?`, `features[]`, `model{name,version,durationMs}`.
  - `referral.ts`: `Doctor` / `Facility` (FHIR-shaped), `Referral`, `ReferralInput`.
  - `chat.ts`: `ChatMessage`, `ChatRole`.
  - `auth.ts`: `AuthUser`.
- **Services** (`src/services/`, no React):
  - `auth-service.ts`: Firebase email/password (sign-in, sign-up, sign-out, observe). Graceful "not configured" when env missing.
  - `referral-service.ts`: curated SatuSehat-styled doctor list + `createReferral()`; every record labeled `Data contoh - sandbox`.
  - `assistant-service.ts`: `AssistantProvider` interface + `ScriptedProvider` (result-aware canned answers). LLM-swappable later.
- **Controllers** (`src/hooks/`): `useResultFlow` (prompt/detail/chat state machine + high-risk trigger), `useAuth`, `useReferral`, `useAssistantChat`. Existing `useAnalysis`, `useAudioRecorder` lightly aligned, behavior unchanged.
- **Views** (`src/components/`): `referral/ReferralPrompt`, `referral/DoctorCard`, `referral/DoctorReferralPanel`, `result/ResultDetail`, `result/ScoreBars`, `result/SpectrogramView`, `chat/AssistantChat`, `chat/ChatBubble`, `auth/LoginForm`, `auth/AuthGate`.

## Overlays

Native `<dialog>` modals (focus trap, Escape, backdrop close, focus return), full-width sheets on mobile, 44px targets, reduced-motion crossfade.

- **ReferralPrompt**: `ConvexSurface panel`, honest headline (`Skenario simulasi: risiko tinggi` + `Simulasi antarmuka — bukan diagnosis medis.`), 3 actions.
- **ResultDetail**: "full model output" badged `Nilai simulasi` (scores + spectrogram-style visual + features + model meta). Actions: `Tutup` / `Analisis dengan AI`.
- **AssistantChat**: aesthetic chat popup; scripted result-aware assistant; message bubbles, quick-reply chips, typing indicator.

## Auth & routes

- Firebase email/password via `NEXT_PUBLIC_FIREBASE_*` env vars; documented setup; graceful "auth belum dikonfigurasi" state (no crash).
- `/masuk`: login page honoring `?next=`. `/rujukan`: auth-gated referral page; redirects to `/masuk` when signed out. Session persistence means a second `Rujuk` skips login.

## Honesty & data integrity

- Every detection/referral/detail surface is labeled simulation/sandbox; no diagnosis claims.
- `AnalysisResult` change is additive only; `POST /api/analyze` contract preserved. Mock route fills `detail` with clearly-labeled simulation values; real backend fills identical fields.

## Refactor (final)

New code + shared glue only. SOLID boundaries (services own side-effects, hooks own state, components presentational, models pure). Full mobile pass. No behavior or visual change from the refactor.

## Validation

`npm run lint` + `npm run build`; manual smoke of the full flow (keyboard + reduced-motion + 320-1440px); honesty check. No automated test runner added.

## Assumptions

- Login is real routes (`/masuk`, `/rujukan`), not a modal.
- "Tutup" is the single dismiss label across overlays.
- ResultDetail "Tutup" returns to the ReferralPrompt.
