from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass


MIN_DURATION_SECONDS = 0.5
MAX_DURATION_SECONDS = 30.0
MIN_RMS = 0.005
SUPPORTED_SAMPLE_WIDTHS = frozenset({1, 2, 3, 4})


class AudioValidationError(ValueError):
    """Raised when uploaded audio is unreadable or too poor for inference."""


@dataclass(frozen=True)
class AudioQuality:
    duration_seconds: float
    sample_rate: int
    channels: int
    rms: float


def validate_wav_audio(data: bytes) -> AudioQuality:
    """Validate a PCM WAV upload without persisting the recording."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(frame_count)
    except (EOFError, wave.Error) as error:
        raise AudioValidationError("File harus berupa WAV PCM yang valid") from error

    if channels not in (1, 2):
        raise AudioValidationError("Audio WAV harus mono atau stereo")
    if sample_rate < 8_000 or sample_rate > 96_000:
        raise AudioValidationError("sample rate WAV tidak didukung")
    if sample_width not in SUPPORTED_SAMPLE_WIDTHS:
        raise AudioValidationError("Bit depth WAV tidak didukung")

    duration_seconds = frame_count / sample_rate
    if not MIN_DURATION_SECONDS <= duration_seconds <= MAX_DURATION_SECONDS:
        raise AudioValidationError(
            f"Audio harus memiliki durasi {MIN_DURATION_SECONDS:g}-{MAX_DURATION_SECONDS:g} detik"
        )

    rms = _calculate_rms(frames, sample_width) if frames else 0.0
    if rms < MIN_RMS:
        raise AudioValidationError("Audio hening atau terlalu pelan untuk dianalisis")

    return AudioQuality(
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        rms=rms,
    )


def _calculate_rms(frames: bytes, sample_width: int) -> float:
    if sample_width == 3:
        values = [
            int.from_bytes(frames[index : index + 3], "little", signed=True)
            for index in range(0, len(frames) - 2, 3)
        ]
        maximum_amplitude = float((1 << 23) - 1)
    else:
        format_code = {1: "B", 2: "h", 4: "i"}[sample_width]
        try:
            values = struct.unpack(
                f"<{len(frames) // sample_width}{format_code}",
                frames,
            )
        except struct.error as error:
            raise AudioValidationError("WAV sample data is truncated") from error
        if sample_width == 1:
            values = tuple(value - 128 for value in values)
        maximum_amplitude = float((1 << (sample_width * 8 - 1)) - 1)

    if not values:
        return 0.0
    mean_square = sum((value / maximum_amplitude) ** 2 for value in values) / len(values)
    return math.sqrt(mean_square)
