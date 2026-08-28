from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


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
    training_dataset: str = "CODA-TB",
    architecture: str = "spectrogram_clinical_baseline_v1",
    initialization: str = "unspecified",
    pretrained_weights: bool | None = None,
    seed: int | None = None,
) -> Path:
    """Write a blocked-by-default manifest for a newly trained candidate."""
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
        "thresholds": {"elevated": 0.35, "higher": 0.65},
        "calibration_status": "not_calibrated",
        "preprocessing": dict(preprocessing),
        "evaluation": dict(evaluation),
        "evaluation_gate": {
            "status": "blocked",
            "external_validation": False,
        },
    }
    destination = Path(manifest_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination
