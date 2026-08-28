from __future__ import annotations

import numpy as np

from src.model import SpectrogramClinicalClassifier
from training.generate_xai import occlusion_sensitivity


def test_occlusion_sensitivity_matches_feature_shape() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=0, input_mode="audio").eval()
    features = np.linspace(0.0, 1.0, 128 * 36, dtype=np.float32).reshape(1, 128, 36)

    sensitivity, probability = occlusion_sensitivity(
        model,
        features,
        frequency_patch=32,
        time_patch=12,
    )

    assert sensitivity.shape == (128, 36)
    assert np.isfinite(sensitivity).all()
    assert 0.0 <= float(sensitivity.min()) <= float(sensitivity.max()) <= 1.0
    assert 0.0 <= probability <= 1.0
