from __future__ import annotations

import numpy as np

from src.metadata import encode_clinical_metadata, validate_metadata
from tests.factories import build_metadata


def build_preprocessing() -> dict:
    return {
        "clinical_feature_order": [
            "sex",
            "age",
            "height",
            "weight",
            "reported_cough_dur",
            "tb_prior",
            "tb_prior_Pul",
            "tb_prior_Extrapul",
            "tb_prior_Unknown",
            "hemoptysis",
            "heart_rate",
            "temperature",
            "weight_loss",
            "smoke_lweek",
            "fever",
            "night_sweats",
            "Numberofcoughsoundscollected",
            "country_IN",
            "country_MG",
            "country_PH",
            "country_SA",
            "country_TZ",
            "country_UG",
            "country_VN",
            "hiv_Negative",
            "hiv_Positive",
            "hiv_Unknown",
        ],
        "numeric_stats": {
            field: {"mean": 0.0, "std": 1.0}
            for field in (
                "age",
                "height",
                "weight",
                "reported_cough_dur",
                "heart_rate",
                "temperature",
            )
        },
        "countries": ["IN", "MG", "PH", "SA", "TZ", "UG", "VN"],
    }


def test_metadata_encoder_returns_expected_dimension_and_one_hot_values() -> None:
    metadata = validate_metadata(build_metadata(Country="PH"))

    encoded = encode_clinical_metadata(metadata, build_preprocessing(), cough_count=3)

    assert encoded.shape == (27,)
    assert encoded.dtype == np.float32
    assert encoded[16] == 3.0
    assert encoded[19] == 1.0
    assert encoded[26] == 1.0
    assert np.isfinite(encoded).all()
