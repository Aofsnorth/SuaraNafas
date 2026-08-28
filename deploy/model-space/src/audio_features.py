from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioFeatureConfig:
    sample_rate: int = 16_000
    duration_seconds: float = 0.55
    n_mels: int = 128
    n_fft: int = 1_024
    hop_length: int = 256
    target_frames: int = 36


def _decode_pcm_wav(data: bytes) -> tuple[np.ndarray, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(frame_count)
    except (EOFError, wave.Error) as error:
        raise ValueError("Audio must be a valid PCM WAV file") from error

    if sample_width not in (1, 2, 3, 4):
        raise ValueError("Unsupported WAV sample width")
    samples = _unpack_samples(frames, sample_width)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), sample_rate


def _unpack_samples(frames: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 3:
        values = [
            int.from_bytes(frames[index : index + 3], "little", signed=True)
            for index in range(0, len(frames) - 2, 3)
        ]
        return np.asarray(values, dtype=np.float32) / ((1 << 23) - 1)
    format_code = {1: "B", 2: "h", 4: "i"}[sample_width]
    values = struct.unpack(f"<{len(frames) // sample_width}{format_code}", frames)
    samples = np.asarray(values, dtype=np.float32)
    if sample_width == 1:
        return (samples - 128.0) / 127.0
    return samples / float((1 << (sample_width * 8 - 1)) - 1)


def _resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    source_positions = np.linspace(0.0, 1.0, len(samples), endpoint=False)
    target_positions = np.linspace(0.0, 1.0, target_length, endpoint=False)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)


def _frame_signal(samples: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    frame_count = 1 + max(0, (len(samples) - frame_length + hop_length - 1) // hop_length)
    padded_length = (frame_count - 1) * hop_length + frame_length
    padded = np.pad(samples, (0, max(0, padded_length - len(samples))))
    starts = np.arange(frame_count) * hop_length
    return np.stack([padded[start : start + frame_length] for start in starts])


def _mel_filterbank(config: AudioFeatureConfig) -> np.ndarray:
    frequencies = np.linspace(0.0, config.sample_rate / 2.0, config.n_fft // 2 + 1)
    mel_min = 2595.0 * math.log10(1.0 + frequencies[0] / 700.0)
    mel_max = 2595.0 * math.log10(1.0 + frequencies[-1] / 700.0)
    mel_points = np.linspace(mel_min, mel_max, config.n_mels + 2)
    hz_points = 700.0 * (10 ** (mel_points / 2595.0) - 1.0)
    bins = np.floor((config.n_fft + 1) * hz_points / config.sample_rate).astype(int)
    filters = np.zeros((config.n_mels, config.n_fft // 2 + 1), dtype=np.float32)
    for index in range(config.n_mels):
        left, center, right = bins[index : index + 3]
        if center > left:
            filters[index, left:center] = np.linspace(0.0, 1.0, center - left)
        if right > center:
            filters[index, center:right] = np.linspace(1.0, 0.0, right - center)
    return filters


def extract_log_mel(data: bytes, config: AudioFeatureConfig) -> np.ndarray:
    """Decode a WAV and return a deterministic normalized (1, mels, frames) tensor."""
    samples, source_rate = _decode_pcm_wav(data)
    samples = _resample(samples, source_rate, config.sample_rate)
    target_length = round(config.duration_seconds * config.sample_rate)
    samples = samples[:target_length]
    if len(samples) < target_length:
        samples = np.pad(samples, (0, target_length - len(samples)))

    window = np.hanning(config.n_fft).astype(np.float32)
    frames = _frame_signal(samples, config.n_fft, config.hop_length) * window
    spectrum = np.abs(np.fft.rfft(frames, n=config.n_fft)) ** 2
    mel = _mel_filterbank(config) @ spectrum.T
    log_mel = 10.0 * np.log10(np.maximum(mel, 1e-10))
    normalized = (log_mel - log_mel.min()) / (log_mel.max() - log_mel.min() + 1e-8)
    if normalized.shape[1] < config.target_frames:
        normalized = np.pad(
            normalized,
            ((0, 0), (0, config.target_frames - normalized.shape[1])),
        )
    else:
        normalized = normalized[:, : config.target_frames]
    return normalized.astype(np.float32)[None, :, :]
