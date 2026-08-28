from __future__ import annotations

from src.audio_validation import AudioQuality
from src.metadata import validate_metadata
from src.model_gateway import PredictionValidationError, ScreeningPrediction
from tests.factories import build_metadata


def test_prediction_rejects_probability_outside_unit_interval() -> None:
    try:
        ScreeningPrediction(
            tb_risk_probability=1.2,
            risk_band="higher",
            accepted_clips=1,
            quality_status="acceptable",
            uncertainty=0.1,
        )
    except PredictionValidationError:
        return
    raise AssertionError("Expected invalid probability to be rejected")


def test_prediction_contract_accepts_valid_output() -> None:
    prediction = ScreeningPrediction(
        tb_risk_probability=0.42,
        risk_band="elevated",
        accepted_clips=2,
        quality_status="acceptable",
        uncertainty=0.2,
        model_name="validated model",
        model_version="2026.08",
        calibration_status="held_out",
    )

    assert prediction.model_version == "2026.08"
