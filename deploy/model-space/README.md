---
title: Deteksi TB Model API
emoji: 🧠
colorFrom: gray
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Deteksi TB — Model API (Hugging Face Space)

FastAPI service that the frontend calls through its `/api/analyze` route.

- Endpoint: `POST /predict`
- Body: `multipart/form-data` with field `audio`
- Response JSON (matches the frontend `AnalysisResult`, minus `source`):
  `{ risk, confidence, message, recommendation, detail? }`

## Wire it to the frontend

On the **frontend** Space, set a variable:

```
BACKEND_API_URL = https://<username>-deteksi-tb-model-api.hf.space
```

The frontend forwards uploads to `${BACKEND_API_URL}/predict` and renders the
result. Returning `risk: "high"` triggers the doctor-referral flow.

## Plug in your model

Replace the placeholder block in `app.py` with real inference (decode audio →
mel-spectrogram → your CNN). Add the ML deps to `requirements.txt`.
