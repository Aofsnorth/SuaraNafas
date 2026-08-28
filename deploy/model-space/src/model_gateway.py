from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from src.audio_validation import AudioQuality
from src.metadata import ClinicalMetadata, SUPPORTED_CODA_COUNTRIES


class ModelInferenceError(RuntimeError):
    """Raised when a configured model cannot produce a safe prediction."""


class PredictionValidationError(ValueError):
    """Raised when a model returns a malformed prediction."""


@dataclass(frozen=True)
class ScreeningPrediction:
    tb_risk_probability: float
    risk_band: str
    accepted_clips: int
    quality_status: str
    uncertainty: float
    model_name: str = "SuaraNafas screening model"
    model_version: str = "unversioned"
    calibration_status: str = "unknown"

    def __post_init__(self) -> None:
        if not 0.0 <= self.tb_risk_probability <= 1.0 or not isfinite(
            self.tb_risk_probability
        ):
            raise PredictionValidationError("Prediction score must be between 0 and 1")
        if self.risk_band not in {"lower", "elevated", "higher"}:
            raise PredictionValidationError("Prediction risk band is invalid")
        if self.accepted_clips < 1:
            raise PredictionValidationError("Prediction must contain an accepted clip")
        if not 0.0 <= self.uncertainty <= 1.0 or not isfinite(self.uncertainty):
            raise PredictionValidationError("Prediction uncertainty must be between 0 and 1")
        if not self.model_name.strip() or not self.model_version.strip():
            raise PredictionValidationError("Model identity is required")


class ScreeningModel(Protocol):
    @property
    def is_available(self) -> bool:
        """Return whether a validated model artifact is ready for inference."""

    @property
    def supported_countries(self) -> frozenset[str]:
        """Return countries represented by the model's validation data."""

    def predict(
        self,
        audio: Sequence[bytes],
        qualities: Sequence[AudioQuality],
        metadata: ClinicalMetadata,
    ) -> ScreeningPrediction:
        """Return a research screening result for a validated request."""


class UnavailableScreeningModel:
    @property
    def is_available(self) -> bool:
        return False

    @property
    def supported_countries(self) -> frozenset[str]:
        return SUPPORTED_CODA_COUNTRIES

    def predict(
        self,
        audio: Sequence[bytes],
        qualities: Sequence[AudioQuality],
        metadata: ClinicalMetadata,
    ) -> ScreeningPrediction:
        raise ModelInferenceError("No validated model artifact is configured")
