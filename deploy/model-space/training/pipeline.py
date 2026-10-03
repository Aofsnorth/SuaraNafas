from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from training.artifact_manifest import _validate_runtime_fields


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_candidate_manifest(
    artifact_path: str | Path,
    manifest_path: str | Path,
    *,
    model_name: str,
    model_version: str,
    input_mode: str,
    metadata_dim: int,
    supported_countries: Sequence[str],
    preprocessing: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    thresholds: Mapping[str, float] | None = None,
    training_dataset: str = "CODA-TB",
    architecture: str = "spectrogram_clinical_baseline_v1",
    initialization: str = "unspecified",
    pretrained_weights: bool | None = None,
    distillation: Mapping[str, Any] | None = None,
    seed: int | None = None,
) -> Path:
    """Write a blocked-by-default manifest for a newly trained candidate.

    ``distillation`` documents a pretrained teacher that guided *training* only.
    The deployed student is still randomly initialised, so
    ``pretrained_weights`` must stay ``False`` for residual architectures.
    """
    artifact = Path(artifact_path).resolve()
    manifest = {
        "model_name": model_name,
        "model_version": model_version,
        "artifact_path": artifact.name,
        "artifact_sha256": _sha256(artifact),
        "training_dataset": training_dataset,
        "split_strategy": "patient_grouped",
        "split_stratified": True,
        "architecture": architecture,
        "initialization": initialization,
        "pretrained_weights": pretrained_weights,
        "training_seed": seed,
        "input_mode": input_mode,
        "metadata_dim": metadata_dim,
        "supported_countries": [country.upper() for country in supported_countries],
        "thresholds": dict(thresholds or {"elevated": 0.35, "higher": 0.65}),
        "calibration_status": "not_calibrated",
        "preprocessing": dict(preprocessing),
        "distillation": dict(distillation or {}),
        "evaluation": dict(evaluation),
        "evaluation_gate": {
            "status": "blocked",
            "external_validation": False,
        },
    }
    # Fail now rather than after the training run, when the model can no
    # longer be served. Uses the exact same contract as the loader, so the
    # two can never disagree about what is acceptable.
    _validate_runtime_fields(
        {
            "architecture": manifest["architecture"],
            "initialization": manifest["initialization"],
            "pretrained_weights": manifest["pretrained_weights"],
            "preprocessing": manifest["preprocessing"],
            "input_mode": manifest["input_mode"],
            "metadata_dim": manifest["metadata_dim"],
            "distillation": manifest["distillation"],
        }
    )
    destination = Path(manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination
