import json
import os
from pathlib import Path

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from model import load_model, predict_tb_risk
from preprocessing import (
    PreprocessingError,
    classify_risk,
    load_deployment_config,
    prepare_model_inputs,
)


BASE_DIR = Path(__file__).resolve().parent
CONFIG = load_deployment_config(BASE_DIR / "deployment_config.json")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL = load_model(BASE_DIR / CONFIG["model"]["weights_file"], DEVICE)

app = FastAPI(title="SuaraNafas TB Screening API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "model": "SuaraNafas multimodal TB screening",
    }


@app.get("/config/public")
def public_config():
    return {
        "countries": CONFIG["countries"],
        "hiv_statuses": CONFIG["hiv_statuses"],
        "recommended_clips": CONFIG["audio"]["recommended_clips"],
        "maximum_clips": CONFIG["audio"]["maximum_clips"],
        "thresholds": CONFIG["thresholds"],
        "disclaimer": CONFIG["disclaimer"],
    }


@app.post("/predict")
async def predict(
    metadata: str = Form(...),
    audio: list[UploadFile] = File(...),
):
    if len(audio) > int(CONFIG["audio"]["maximum_clips"]):
        raise HTTPException(status_code=422, detail="Too many audio clips")

    try:
        clinical_payload = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="metadata must be valid JSON") from exc

    audio_bytes = []
    for upload in audio:
        if upload.content_type and not (
            upload.content_type.startswith("audio/")
            or upload.content_type == "application/octet-stream"
        ):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {upload.content_type}",
            )
        audio_bytes.append(await upload.read())

    try:
        prepared = prepare_model_inputs(audio_bytes, clinical_payload, CONFIG)
        probability = predict_tb_risk(
            MODEL,
            prepared.patient_specs,
            prepared.metadata,
        )
    except PreprocessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "tb_risk_probability": probability,
        "tb_risk_percent": round(probability * 100, 2),
        "risk_band": classify_risk(probability, CONFIG),
        "accepted_clips": prepared.accepted_clips,
        "thresholds": CONFIG["thresholds"],
        "disclaimer": CONFIG["disclaimer"],
        "limitations": [
            "This is screening, not microbiological confirmation.",
            "The model was validated on CODA-TB data.",
            "Clinical metadata contributes strongly to the prediction.",
        ],
    }
