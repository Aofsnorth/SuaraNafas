from __future__ import annotations

import numpy as np

from src.audio_features import AudioFeatureConfig, extract_log_mel
from tests.factories import build_wav


def test_log_mel_features_have_stable_model_shape() -> None:
    features = extract_log_mel(build_wav(), AudioFeatureConfig())

    assert features.shape == (1, 128, 36)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    assert float(features.min()) >= 0.0
    assert float(features.max()) <= 1.0


def test_log_mel_features_are_deterministic_for_same_audio() -> None:
    audio = build_wav(frequency_hz=330.0)

    first = extract_log_mel(audio, AudioFeatureConfig())
    second = extract_log_mel(audio, AudioFeatureConfig())

    assert np.array_equal(first, second)
