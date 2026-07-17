# Agent Handoff: Integrate SuaraNafas with Next.js + Hugging Face Spaces

## Objective

Build a hackathon-ready full-stack application for **multimodal TB risk screening**.

- Frontend and server routes: Next.js with TypeScript.
- PyTorch inference backend: Hugging Face Docker Space.
- Optional chatbot: external LLM endpoint called only from a server-side Next.js route.
- Never call the output a TB diagnosis.

## Existing inference assets

This directory contains:

- `model.py` — exact inference architecture and weight loader.
- `preprocessing.py` — audio + clinical preprocessing.
- `app.py` — FastAPI API for Hugging Face Spaces.
- `tb_cough_edge_weights_fp32.pt` — compact trained weights (~15 MB).
- `export_deployment_config.py` — creates exact metadata statistics/config.
- `deployment_config.json` — must be generated before deployment.
- `requirements.txt`, `Dockerfile` — HF Docker Space runtime.
- `test_model_load.py` — model load smoke test.

Do not reconstruct the model in TypeScript. The browser sends inputs to the Python API.

## Required preparation

From this directory, run:

```bash
python export_deployment_config.py
python test_model_load.py
uvicorn app:app --host 0.0.0.0 --port 7860
```

Confirm:

```text
GET http://localhost:7860/health
```

returns `{"status":"ok", ...}`.

## Recommended deployment architecture

```text
Browser
  -> Next.js UI
  -> Next.js /api/screen proxy
  -> Hugging Face Space /predict
  -> PyTorch model

Browser
  -> Next.js chatbot UI
  -> Next.js /api/chat
  -> external LLM provider
```

The browser should not receive model weights or provider API keys.

## Hugging Face Space

Create a **Docker Space**, then upload the complete contents of this directory.

Space README front matter should contain:

```yaml
---
title: SuaraNafas Inference
sdk: docker
app_port: 7860
---
```

Set Space variable:

```text
ALLOWED_ORIGINS=https://your-nextjs-domain.vercel.app,http://localhost:3000
```

The API will expose:

<!--- `GET /health`
- `GET /config/public`-->
- `POST /predict`

## Prediction API contract

### Request

`POST /predict` using `multipart/form-data`.

Fields:

- `metadata`: JSON string.
- `audio`: one or more audio files. Repeated multipart field name.

Example metadata:

```json
{
  "sex": "Male",
  "age": 32,
  "height": 170,
  "weight": 58,
  "reported_cough_dur": 14,
  "tb_prior": "No",
  "tb_prior_Pul": "No",
  "tb_prior_Extrapul": "No",
  "tb_prior_Unknown": "No",
  "hemoptysis": "No",
  "heart_rate": 88,
  "temperature": 37.1,
  "weight_loss": "Yes",
  "smoke_lweek": "No",
  "fever": "Yes",
  "night_sweats": "Yes",
  "Country": "ID_NOT_SUPPORTED",
  "HIVstatus": "Unknown"
}
```

Important: the current model only supports CODA-TB country categories:

```text
IN, MG, PH, SA, TZ, UG, VN
```

For an Indonesian hackathon user, do not silently map Indonesia to India (`IN`). Until the model is retrained with Indonesian data, you should rather add an agreed fallback strategy in Python and clearly disclose that it is out-of-distribution.

Do not invent a country mapping without product approval.

### Response

```json
{
  "tb_risk_probability": 0.42,
  "tb_risk_percent": 42.0,
  "risk_band": "elevated",
  "accepted_clips": 5,
  "thresholds": {
    "screening": 0.2596,
    "balanced": 0.4084,
    "default": 0.5,
    "max_accuracy": 0.6803
  },
  "disclaimer": "...",
  "limitations": ["..."]
}
```

### Error response

FastAPI returns:

```json
{
  "detail": "human-readable error"
}
```

with status 415 or 422 for bad input.

## Next.js implementation

Use App Router and TypeScript.

Suggested structure:

```text
web/
├── app/
│   ├── api/
│   │   ├── screen/route.ts
│   │   └── chat/route.ts
│   ├── screen/page.tsx
│   └── page.tsx
├── components/
│   ├── ClinicalForm.tsx
│   ├── CoughRecorder.tsx
│   ├── ScreeningResult.tsx
│   └── ScreeningChat.tsx
└── lib/
    ├── screening-types.ts
    └── validation.ts
```

Environment variables:

```text
TB_INFERENCE_URL=https://YOUR_SPACE.hf.space
LLM_BASE_URL=https://provider.example/v1
LLM_API_KEY=secret
LLM_MODEL=model-name
```

Never prefix secrets with `NEXT_PUBLIC_`.

## Next.js screening proxy example

```ts
// app/api/screen/route.ts
export const runtime = "nodejs";

export async function POST(request: Request) {
  const incoming = await request.formData();
  const upstream = new FormData();

  const metadata = incoming.get("metadata");
  if (typeof metadata !== "string") {
    return Response.json({ error: "Missing metadata" }, { status: 400 });
  }
  upstream.append("metadata", metadata);

  for (const audio of incoming.getAll("audio")) {
    if (audio instanceof File) upstream.append("audio", audio);
  }

  const response = await fetch(`${process.env.TB_INFERENCE_URL}/predict`, {
    method: "POST",
    body: upstream,
    cache: "no-store",
  });

  const result = await response.json();
  return Response.json(result, { status: response.status });
}
```

## Browser recording

Preferred hackathon workflow:

- Ask for five separately recorded coughs.
- Use `MediaRecorder`.
- Send each recording under multipart field `audio`.
- Backend converts to mono 16 kHz and crops/pads to 0.55 seconds.
- The backend rejects silent audio.

Browser recordings may be WebM/Opus. The HF Docker image includes FFmpeg, but `soundfile` may not decode every browser codec directly. If WebM decode fails, update `_load_audio_source` in `preprocessing.py` to decode via FFmpeg/Pydub, or record WAV in the client using a compatible recorder library.

Prefer WAV uploads for the first reliable demo.

## Chatbot integration

The chatbot must be called from `app/api/chat/route.ts`, never directly from the browser.

Only send structured screening output to the LLM. Do not send raw cough audio or unnecessary clinical identifiers.

System policy:

```text
You explain preliminary TB screening results.
Never claim to diagnose or exclude TB.
Never prescribe medication.
Recommend professional assessment and microbiological testing when risk or symptoms warrant it.
State uncertainty and model limitations.
Do not infer information that is absent from the structured screening result.
If the user reports severe symptoms such as coughing blood, severe shortness of breath, confusion, or emergency signs, advise urgent local medical care.
```

The chat route should accept:

```ts
type ChatRequest = {
  messages: Array<{ role: "user" | "assistant"; content: string }>;
  screeningResult?: ScreeningResult;
};
```

## UI requirements

1. Consent and privacy notice before recording.
2. Clinical questionnaire with required-field validation.
3. Five-cough recorder/upload flow with retry controls.
4. Loading and HF cold-start states.
5. Result shown as screening risk, not diagnosis.
6. Show screening disclaimer prominently.
7. Show accepted clip count and audio errors.
8. Chatbot explanation is optional and visibly AI-generated.
9. Do not persist audio by default.
10. Do not log clinical payloads or raw audio.

## Product wording

Use:

- “TB risk screening”
- “lower / elevated / higher screening risk”
- “seek confirmatory microbiological testing”

Avoid:

- “TB positive”
- “TB negative”
- “diagnosed”
- “healthy”
- “medical certainty”

## Known model limitations

- Validation AUROC varies by training run; latest supplied result was about 0.85.
- Clinical metadata carries most of the predictive signal.
- Country is a confounder and supported countries are limited.
- Audio-only performance is weak in the current diagnostic analysis.
- Thresholds were chosen and evaluated on the same validation set.
- This is a hackathon prototype, not a regulated medical device.

Surface these honestly in the app’s “About model” section.

## Acceptance criteria

- `deployment_config.json` exists and has full-precision means/stds.
- `test_model_load.py` passes.
<!--- HF `/health` returns 200.-->
- HF `/predict` accepts five WAV clips plus metadata.
- Next.js proxy does not expose backend/provider secrets.
- Result includes probability, risk band, thresholds, disclaimer.
- Invalid/silent audio produces an actionable error.
- Chatbot never claims a diagnosis in basic safety tests.
- End-to-end demo works from mobile Chrome and desktop Chrome.
- A backup demo video exists in case HF Space cold-starts.
