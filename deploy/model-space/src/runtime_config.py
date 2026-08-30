from __future__ import annotations

import os
from pathlib import Path

from src.model_gateway import ScreeningModel, UnavailableScreeningModel
from src.model_runtime import (
    ModelConfigurationError,
    load_torch_screening_model,
)


def _candidate_mode_enabled() -> bool:
    deployment_environment = os.getenv("DEPLOYMENT_ENV", "").strip().casefold()
    explicitly_enabled = (
        os.getenv("ALLOW_BLOCKED_CANDIDATE", "").strip().casefold() == "true"
    )
    return explicitly_enabled and deployment_environment in {"development", "staging"}


def load_configured_model() -> ScreeningModel:
    """Load a validated model or an explicitly enabled local research candidate."""
    manifest_value = os.getenv("MODEL_MANIFEST_PATH", "").strip()
    if not manifest_value:
        return UnavailableScreeningModel()

    try:
        return load_torch_screening_model(
            Path(manifest_value),
            device=os.getenv("MODEL_DEVICE", "cpu"),
            allow_blocked_candidate=_candidate_mode_enabled(),
        )
    except (ModelConfigurationError, ValueError, OSError):
        return UnavailableScreeningModel()
