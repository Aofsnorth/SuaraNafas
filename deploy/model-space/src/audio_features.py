from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np


LEGACY_LOG_MEL_V1 = "legacy_numpy_log_mel_v1"
ENERGY_LOG_MEL_V2 = "energy_numpy_log_mel_v2"
TBSCREEN_LOG_MEL_V1 = "tbscreen_log_mel_v1"
SUPPORTED_AUDIO_RECIPES = frozenset(
    {LEGACY_LOG_MEL_V1, ENERGY_LOG_MEL_V2, TBSCREEN_LOG_MEL_V1}
)


@dataclass(frozen=True)
class AudioFeatureConfig:
    recipe: str = ENERGY_LOG_MEL_V2
    sample_rate: int = 16_000
    duration_seconds: float = 1.5
    n_mels: int = 128
    n_fft: int = 1_024
    hop_length: int = 256
    target_frames: int = 91
    win_length: int | None = None
    center: bool = False
    pad_mode: str = "constant"
    mel_scale: str = "htk"
    mel_norm: str | None = None
    f_min: float = 0.0
    f_max: float | None = None
    power: float = 2.0
    top_db: float | None = None
    normalization: str = "per_clip_minmax"
    resampling: str = "linear_v1"
    window: str = "hann_symmetric"
    window_selection: str = "highest_energy_v1"

    def __post_init__(self) -> None:
        if self.recipe not in SUPPORTED_AUDIO_RECIPES:
            raise ValueError(f"unsupported audio preprocessing recipe: {self.recipe}")
        integer_values = (
            self.sample_rate,
            self.n_mels,
            self.n_fft,
            self.hop_length,
            self.target_frames,
        )
        if any(isinstance(value, bool) or value < 1 for value in integer_values):
            raise ValueError("audio dimensions and sample rate must be positive integers")
        if self.duration_seconds <= 0.0:
            raise ValueError("duration_seconds must be positive")
        if self.win_length is not None and not 1 <= self.win_length <= self.n_fft:
            raise ValueError("win_length must be between one and n_fft")
        if self.f_min < 0.0 or self.f_max is not None and self.f_max <= self.f_min:
            raise ValueError("mel frequency bounds are invalid")
        if self.power != 2.0 or self.normalization != "per_clip_minmax":
            raise ValueError("only power spectrograms with per-clip min-max are supported")
        if self.window_selection != "highest_energy_v1":
            raise ValueError("unsupported audio window selection")

    @classmethod
    def tb_screen_reference(cls) -> AudioFeatureConfig:
        return cls(
            recipe=TBSCREEN_LOG_MEL_V1,
            sample_rate=44_100,
            duration_seconds=1.0,
            n_mels=64,
            n_fft=2_048,
            win_length=1_102,
            hop_length=441,
            target_frames=101,
            center=True,
            pad_mode="reflect",
            mel_scale="htk",
            mel_norm="slaney",
            f_min=0.0,
            f_max=22_050.0,
            power=2.0,
            top_db=80.0,
            normalization="per_clip_minmax",
            resampling="fir_linear_v1",
            window="hann_periodic",
            window_selection="highest_energy_v1",
        )

    @classmethod
    def from_manifest(
        cls,
        payload: Mapping[str, Any],
        *,
        strict: bool = False,
    ) -> AudioFeatureConfig:
        if strict:
            missing = set(asdict(cls.tb_screen_reference())) - set(payload)
            if missing:
                raise ValueError(
                    "audio preprocessing is missing required fields: "
                    + ", ".join(sorted(missing))
                )
        defaults = asdict(cls())
        values = {field: payload.get(field, default) for field, default in defaults.items()}
        if "recipe" not in payload:
            values["recipe"] = LEGACY_LOG_MEL_V1
        try:
            return cls(**values)
        except TypeError as error:
            raise ValueError("audio preprocessing fields have invalid types") from error

    def to_manifest(self) -> dict[str, Any]:
        return asdict(self)


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

    if channels < 1 or sample_rate < 1 or sample_width not in (1, 2, 3, 4):
        raise ValueError("Unsupported WAV encoding")
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


def _linear_resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    source_positions = np.linspace(0.0, 1.0, len(samples), endpoint=False)
    target_positions = np.linspace(0.0, 1.0, target_length, endpoint=False)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)


def _anti_aliased_resample(
    samples: np.ndarray,
    source_rate: int,
    target_rate: int,
) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    filtered = samples
    if target_rate < source_rate:
        radius = 64
        ratio = target_rate / source_rate
        cutoff = 0.5 * ratio * 0.94
        offsets = np.arange(-radius, radius + 1, dtype=np.float64)
        kernel = 2.0 * cutoff * np.sinc(2.0 * cutoff * offsets)
        kernel *= np.kaiser(kernel.size, 8.6)
        kernel /= kernel.sum()
        filtered = np.convolve(samples, kernel, mode="same")
    target_length = max(1, round(len(samples) * target_rate / source_rate))
    source_positions = np.arange(len(filtered), dtype=np.float64)
    target_positions = np.arange(target_length, dtype=np.float64) * source_rate / target_rate
    return np.interp(target_positions, source_positions, filtered).astype(np.float32)


def _frame_signal(samples: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    frame_count = 1 + max(0, (len(samples) - frame_length + hop_length - 1) // hop_length)
    padded_length = (frame_count - 1) * hop_length + frame_length
    padded = np.pad(samples, (0, max(0, padded_length - len(samples))))
    starts = np.arange(frame_count) * hop_length
    return np.stack([padded[start : start + frame_length] for start in starts])


def _legacy_mel_filterbank(config: AudioFeatureConfig) -> np.ndarray:
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


def _htk_mel_filterbank(config: AudioFeatureConfig) -> np.ndarray:
    maximum_frequency = config.f_max or config.sample_rate / 2.0
    frequencies = np.linspace(0.0, config.sample_rate / 2.0, config.n_fft // 2 + 1)
    mel_min = 2595.0 * np.log10(1.0 + config.f_min / 700.0)
    mel_max = 2595.0 * np.log10(1.0 + maximum_frequency / 700.0)
    mel_points = np.linspace(mel_min, mel_max, config.n_mels + 2)
    hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
    frequency_deltas = np.diff(hz_points)
    slopes = hz_points[:, None] - frequencies[None, :]
    down_slopes = -slopes[:-2] / frequency_deltas[:-1, None]
    up_slopes = slopes[2:] / frequency_deltas[1:, None]
    filters = np.maximum(0.0, np.minimum(down_slopes, up_slopes))
    if config.mel_norm == "slaney":
        filters *= (2.0 / (hz_points[2:] - hz_points[:-2]))[:, None]
    return filters.astype(np.float32)


def _prefix_window(samples: np.ndarray, target_length: int) -> np.ndarray:
    selected = samples[:target_length]
    return np.pad(selected, (0, max(0, target_length - len(selected))))


def _highest_energy_window(samples: np.ndarray, target_length: int) -> np.ndarray:
    if len(samples) <= target_length:
        return np.pad(samples, (0, target_length - len(samples)))
    squared = samples.astype(np.float64) ** 2
    cumulative_energy = np.pad(np.cumsum(squared), (1, 0))
    window_energy = cumulative_energy[target_length:] - cumulative_energy[:-target_length]
    start = int(np.argmax(window_energy))
    return samples[start : start + target_length]


def _normalize_and_resize(values: np.ndarray, target_frames: int) -> np.ndarray:
    minimum = float(values.min())
    scale = float(values.max()) - minimum
    normalized = np.zeros_like(values) if scale <= 1e-12 else (values - minimum) / scale
    if normalized.shape[1] < target_frames:
        normalized = np.pad(normalized, ((0, 0), (0, target_frames - normalized.shape[1])))
    else:
        normalized = normalized[:, :target_frames]
    return normalized.astype(np.float32)[None, :, :]


def _extract_legacy_log_mel(samples: np.ndarray, config: AudioFeatureConfig) -> np.ndarray:
    window = np.hanning(config.n_fft).astype(np.float32)
    frames = _frame_signal(samples, config.n_fft, config.hop_length) * window
    spectrum = np.abs(np.fft.rfft(frames, n=config.n_fft)) ** 2
    mel = _legacy_mel_filterbank(config) @ spectrum.T
    log_mel = 10.0 * np.log10(np.maximum(mel, 1e-10))
    return _normalize_and_resize(log_mel, config.target_frames)


def _extract_tb_screen_log_mel(samples: np.ndarray, config: AudioFeatureConfig) -> np.ndarray:
    if not config.center or config.pad_mode != "reflect":
        raise ValueError("TBscreen preprocessing requires centered reflect padding")
    if config.window != "hann_periodic" or config.mel_scale != "htk":
        raise ValueError("TBscreen preprocessing requires periodic Hann and HTK mel")
    if config.win_length is None or config.mel_norm != "slaney" or config.top_db is None:
        raise ValueError("TBscreen preprocessing parameters are incomplete")

    padded = np.pad(samples, (config.n_fft // 2, config.n_fft // 2), mode="reflect")
    frame_count = 1 + (len(padded) - config.n_fft) // config.hop_length
    frames = np.stack(
        [
            padded[index * config.hop_length : index * config.hop_length + config.n_fft]
            for index in range(frame_count)
        ]
    )
    periodic_hann = np.hanning(config.win_length + 1)[:-1]
    window = np.pad(
        periodic_hann,
        (
            (config.n_fft - config.win_length) // 2,
            config.n_fft - config.win_length - (config.n_fft - config.win_length) // 2,
        ),
    )
    spectrum = np.abs(np.fft.rfft(frames * window, n=config.n_fft)) ** config.power
    mel = _htk_mel_filterbank(config) @ spectrum.T
    decibels = 10.0 * np.log10(np.maximum(mel, 1e-10))
    decibels = np.maximum(decibels, float(decibels.max()) - config.top_db)
    return _normalize_and_resize(decibels, config.target_frames)


def extract_log_mel(data: bytes, config: AudioFeatureConfig) -> np.ndarray:
    """Decode a WAV and return a deterministic normalized model tensor."""
    samples, source_rate = _decode_pcm_wav(data)
    if config.recipe == LEGACY_LOG_MEL_V1:
        samples = _linear_resample(samples, source_rate, config.sample_rate)
    else:
        samples = _anti_aliased_resample(samples, source_rate, config.sample_rate)
    target_length = round(config.duration_seconds * config.sample_rate)
    samples = (
        _prefix_window(samples, target_length)
        if config.recipe == LEGACY_LOG_MEL_V1
        else _highest_energy_window(samples, target_length)
    )
    if config.recipe == TBSCREEN_LOG_MEL_V1:
        return _extract_tb_screen_log_mel(samples, config)
    return _extract_legacy_log_mel(samples, config)
