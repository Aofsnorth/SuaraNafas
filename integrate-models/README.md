---
title: SuaraNafas Inference
emoji: 🫁
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# SuaraNafas TB Risk Screening API

FastAPI + PyTorch backend for a multimodal TB risk-screening prototype.

## Before deploying

Generate the exact deployment configuration from the original CODA-TB CSVs:

```bash
python export_deployment_config.py
```

Confirm these files exist:

```text
app.py
model.py
preprocessing.py
deployment_config.json
tb_cough_edge_weights_fp32.pt
requirements.txt
Dockerfile
```

Run smoke tests:

```bash
python test_model_load.py
uvicorn app:app --host 0.0.0.0 --port 7860
```

Then open:

```text
http://localhost:7860/docs
```

## API

<!--- `GET /health`
- `GET /config/public`-->
- `POST /predict`

See `AGENT_HANDOFF_NEXTJS_HF.md` for the complete Next.js integration contract.

## Medical disclaimer

This is a hackathon prototype for preliminary screening. It is not a diagnosis,
does not replace microbiological testing, and is not a regulated medical device.
