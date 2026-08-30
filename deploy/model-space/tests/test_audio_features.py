from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from src.audio_features import (
    LEGACY_LOG_MEL_V1,
    AudioFeatureConfig,
    _anti_aliased_resample,
    _linear_resample,
    extract_log_mel,
)
from tests.factories import build_wav


def test_log_mel_features_have_stable_model_shape() -> None:
    features = extract_log_mel(build_wav(), AudioFeatureConfig())

    assert features.shape == (1, 128, 91)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    assert float(features.min()) >= 0.0
    assert float(features.max()) <= 1.0


def test_log_mel_features_are_deterministic_for_same_audio() -> None:
    audio = build_wav(frequency_hz=330.0)

    first = extract_log_mel(audio, AudioFeatureConfig())
    second = extract_log_mel(audio, AudioFeatureConfig())

    assert np.array_equal(first, second)


def test_tb_screen_reference_recipe_has_stable_shape_and_round_trips() -> None:
    config = AudioFeatureConfig.tb_screen_reference()
    audio = build_wav(sample_rate=48_000, frequency_hz=440.0)

    features = extract_log_mel(audio, config)
    restored = AudioFeatureConfig.from_manifest(config.to_manifest(), strict=True)

    assert restored == config
    assert features.shape == (1, 64, 101)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    assert float(features.min()) >= 0.0
    assert float(features.max()) <= 1.0


def test_tb_screen_reference_recipe_rejects_incomplete_manifest() -> None:
    payload = AudioFeatureConfig.tb_screen_reference().to_manifest()
    del payload["win_length"]

    with pytest.raises(ValueError, match="win_length"):
        AudioFeatureConfig.from_manifest(payload, strict=True)


def test_anti_aliased_downsampling_suppresses_above_nyquist_tone() -> None:
    source_rate = 48_000
    target_rate = 16_000
    time = np.arange(source_rate, dtype=np.float64) / source_rate
    samples = np.sin(2.0 * np.pi * 12_000.0 * time).astype(np.float32)

    aliased = _linear_resample(samples, source_rate, target_rate)
    filtered = _anti_aliased_resample(samples, source_rate, target_rate)

    assert float(np.sqrt(np.mean(filtered**2))) < 0.1 * float(
        np.sqrt(np.mean(aliased**2))
    )


def test_log_mel_selects_delayed_signal_instead_of_initial_silence() -> None:
    sample_rate = 16_000
    silence = np.zeros(sample_rate, dtype=np.int16)
    time = np.arange(round(1.5 * sample_rate), dtype=np.float64) / sample_rate
    signal = (0.5 * np.iinfo(np.int16).max * np.sin(2 * np.pi * 440.0 * time)).astype(
        np.int16
    )

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(np.concatenate((silence, signal)).tobytes())
        delayed_audio = buffer.getvalue()

    delayed_features = extract_log_mel(delayed_audio, AudioFeatureConfig())
    signal_features = extract_log_mel(
        build_wav(duration_seconds=1.5, amplitude=0.5, frequency_hz=440.0),
        AudioFeatureConfig(),
    )

    assert np.allclose(delayed_features, signal_features, atol=1e-4)

    legacy_config = AudioFeatureConfig.from_manifest(
        {
            "sample_rate": 16_000,
            "duration_seconds": 1.5,
            "n_mels": 128,
            "n_fft": 1_024,
            "hop_length": 256,
            "target_frames": 91,
        }
    )
    legacy_features = extract_log_mel(delayed_audio, legacy_config)

    assert legacy_config.recipe == LEGACY_LOG_MEL_V1
    assert not np.allclose(legacy_features, signal_features, atol=1e-4)
