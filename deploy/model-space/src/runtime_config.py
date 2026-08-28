from __future__ import annotations

import os
from pathlib import Path

from src.model_runtime import ModelConfigurationError, TorchScreeningModel, load_torch_screening_model
from src.model_gateway import ScreeningModel, UnavailableScreeningModel


def load_configured_model() -> ScreeningModel:
    """Load a validated model when configured; otherwise keep API in degraded mode."""
    manifest_value = os.getenv("MODEL_MANIFEST_PATH", "").strip()
    if not manifest_value:
        return UnavailableScreeningModel()

    try:
        return load_torch_screening_model(
            Path(manifest_value),
            device=os.getenv("MODEL_DEVICE", "cpu"),
        )
    except (ModelConfigurationError, ValueError, OSError):
        return UnavailableScreeningModel()
