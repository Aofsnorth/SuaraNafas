from __future__ import annotations

import io
import json
import math
import struct
import wave
from typing import Any


def build_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
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
        "weight_loss": "Yes",
        "smoke_lweek": "No",
        "fever": "Yes",
        "night_sweats": "Yes",
        "HIVstatus": "Unknown",
        "Country": "PH",
        "heart_rate": 88,
        "temperature": 37.1,
    }
    metadata.update(overrides)
    return metadata


def build_metadata_json(**overrides: Any) -> str:
    return json.dumps(build_metadata(**overrides))


def build_wav(
    *,
    duration_seconds: float = 1.0,
    sample_rate: int = 16_000,
    amplitude: float = 0.25,
    frequency_hz: float = 220.0,
) -> bytes:
    frame_count = round(duration_seconds * sample_rate)
    samples = [
        int(32_767 * amplitude * math.sin(2 * math.pi * frequency_hz * index / sample_rate))
        for index in range(frame_count)
    ]

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()
