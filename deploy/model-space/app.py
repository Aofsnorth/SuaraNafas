from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.audio_validation import AudioValidationError, validate_wav_audio
from src.metadata import MetadataValidationError, validate_metadata
from src.model_gateway import (
    ModelInferenceError,
    PredictionValidationError,
    ScreeningModel,
)
from src.runtime_config import load_configured_model


MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_AUDIO_CLIPS = 8
ACCEPTED_CONTENT_TYPES = frozenset(
    {"audio/wav", "audio/wave", "audio/x-wav", "application/octet-stream"}
)
DISCLAIMER = (
    "Research screening support only; this is not a TB diagnosis or rule-out. "
    "Seek clinical assessment and WHO-recommended confirmatory testing."
)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _parse_metadata(raw_metadata: str | None) -> dict[str, Any]:
    if not raw_metadata:
        raise _error(422, "INVALID_METADATA", "metadata is required")
    try:
        payload = json.loads(raw_metadata)
    except json.JSONDecodeError as error:
        raise _error(422, "INVALID_METADATA", "metadata must be valid JSON") from error
    if not isinstance(payload, dict):
        raise _error(422, "INVALID_METADATA", "metadata must be a JSON object")
    return payload


async def _read_audio_uploads(uploads: list[UploadFile] | None) -> list[bytes]:
    if not uploads:
        raise _error(422, "INVALID_AUDIO", "at least one audio file is required")
    if len(uploads) > MAX_AUDIO_CLIPS:
        raise _error(
            422,
            "TOO_MANY_AUDIO_CLIPS",
            f"at most {MAX_AUDIO_CLIPS} audio clips are accepted",
        )

    audio_bytes: list[bytes] = []
    total_bytes = 0
    for upload in uploads:
        if upload.content_type not in ACCEPTED_CONTENT_TYPES:
            raise _error(415, "UNSUPPORTED_AUDIO_TYPE", "audio must be a PCM WAV file")

        content_length = upload.size
        if content_length is not None and content_length > MAX_AUDIO_BYTES:
            raise _error(413, "AUDIO_TOO_LARGE", "audio exceeds the 15 MB limit")

        data = await upload.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise _error(413, "AUDIO_TOO_LARGE", "audio exceeds the 15 MB limit")
        if not data:
            raise _error(422, "INVALID_AUDIO", "audio must not be empty")

        total_bytes += len(data)
        if total_bytes > MAX_AUDIO_BYTES:
            raise _error(413, "AUDIO_TOO_LARGE", "total audio exceeds the 15 MB limit")
        audio_bytes.append(data)

    return audio_bytes


def create_app(model: ScreeningModel | None = None) -> FastAPI:
    screening_model = model or load_configured_model()
    app = FastAPI(
        title="SuaraNafas Research Screening API",
        version="0.1.0",
        description=DISCLAIMER,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        deployment_status = screening_model.deployment_status
        return {
            "status": "ok" if deployment_status == "validated" else "degraded",
            "service": "SuaraNafas research screening API",
            "model_status": deployment_status,
            "prediction_enabled": screening_model.is_available,
        }

    @app.post("/predict")
    async def predict(
        metadata: str | None = Form(default=None),
        audio: list[UploadFile] | None = File(default=None),
    ) -> dict[str, Any]:
        payload = _parse_metadata(metadata)
        try:
            clinical_metadata = validate_metadata(payload)
        except MetadataValidationError as error:
            raise _error(422, "INVALID_METADATA", str(error)) from error

        supported_countries = screening_model.supported_countries
        if clinical_metadata.country not in supported_countries:
            raise _error(
                422,
                "OUT_OF_DISTRIBUTION",
                "Country is outside the validated model training distribution",
            )

        audio_bytes = await _read_audio_uploads(audio)
        qualities = []
        for data in audio_bytes:
            try:
                qualities.append(validate_wav_audio(data))
            except AudioValidationError as error:
                raise _error(422, "INVALID_AUDIO", str(error)) from error

        if not screening_model.is_available:
            raise _error(
                503,
                "MODEL_UNAVAILABLE",
                "No externally validated TB screening model is configured.",
            )

        try:
            prediction = screening_model.predict(audio_bytes, qualities, clinical_metadata)
        except (ModelInferenceError, PredictionValidationError) as error:
            raise _error(503, "INFERENCE_UNAVAILABLE", str(error)) from error

        return {
            "tb_risk_probability": prediction.tb_risk_probability,
            "tb_risk_percent": round(prediction.tb_risk_probability * 100, 2),
            "risk_band": prediction.risk_band,
            "accepted_clips": prediction.accepted_clips,
            "quality_status": prediction.quality_status,
            "uncertainty": prediction.uncertainty,
            "out_of_distribution": False,
            "disclaimer": DISCLAIMER,
            "model_name": prediction.model_name,
            "model_version": prediction.model_version,
            "model_status": screening_model.deployment_status,
            "model": {
                "name": prediction.model_name,
                "version": prediction.model_version,
                "calibration_status": prediction.calibration_status,
                "status": screening_model.deployment_status,
            },
        }

    return app


app = create_app()
