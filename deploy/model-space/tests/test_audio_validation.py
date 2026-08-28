from __future__ import annotations

import io
import struct
import wave

import pytest

from src.audio_validation import AudioValidationError, validate_wav_audio
from tests.factories import build_wav


def build_unsigned_8bit_wav(*, amplitude: int = 0, duration_seconds: float = 1.0) -> bytes:
    frame_count = round(duration_seconds * 8_000)
    samples = bytes(
        128 + round(amplitude * ((index % 2) * 2 - 1))
        for index in range(frame_count)
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(8_000)
        wav_file.writeframes(samples)
    return buffer.getvalue()


def test_accepts_audible_wav_and_returns_quality_metrics() -> None:
    result = validate_wav_audio(build_wav())

    assert result.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert result.sample_rate == 16_000
    assert result.channels == 1
    assert result.rms > 0.1


def test_rejects_silent_audio() -> None:
    with pytest.raises(AudioValidationError, match="terlalu pelan"):
        validate_wav_audio(build_wav(amplitude=0.0))


def test_rejects_silent_unsigned_8bit_audio() -> None:
    with pytest.raises(AudioValidationError, match="terlalu pelan"):
        validate_wav_audio(build_unsigned_8bit_wav())


def test_rejects_malformed_wav() -> None:
    with pytest.raises(AudioValidationError, match="WAV"):
        validate_wav_audio(b"not-a-wav")


def test_rejects_audio_outside_duration_limit() -> None:
    with pytest.raises(AudioValidationError, match="durasi"):
        validate_wav_audio(build_wav(duration_seconds=0.1))


def test_rejects_nan_like_metadata_is_not_relevant_to_audio() -> None:
    data = bytearray(build_wav())
    data[24:28] = struct.pack("<I", 0)

    with pytest.raises(AudioValidationError, match="sample rate"):
        validate_wav_audio(bytes(data))
