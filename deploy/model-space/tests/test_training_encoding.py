from __future__ import annotations

import numpy as np

from training.encoding import ClinicalPreprocessor
from tests.factories import build_metadata


def test_preprocessor_fits_stats_on_rows_and_returns_fixed_vector() -> None:
    rows = [
        build_metadata(age=20, Country="PH"),
        build_metadata(age=40, Country="IN"),
    ]
    preprocessor = ClinicalPreprocessor.fit(rows)

    vector = preprocessor.transform(build_metadata(age=30, Country="PH"), cough_count=5)

    assert vector.shape == (27,)
    assert vector.dtype == np.float32
    assert vector[1] == 0.0
    assert vector[16] == 5.0
    assert vector[19] == 1.0
    assert vector[17] == 0.0
    assert np.isfinite(vector).all()


def test_preprocessor_uses_training_mean_for_missing_numeric_value() -> None:
    rows = [build_metadata(age=20), build_metadata(age=40)]
    preprocessor = ClinicalPreprocessor.fit(rows)

    vector = preprocessor.transform({**build_metadata(), "age": ""}, cough_count=1)

    assert vector[1] == 0.0
