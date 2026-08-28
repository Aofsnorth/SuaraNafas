from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Mapping


class ArtifactManifestError(ValueError):
    """Raised when a model manifest does not meet deployment safety gates."""


@dataclass(frozen=True)
class ArtifactManifest:
    model_name: str
    model_version: str
    artifact_path: str
    artifact_sha256: str
    training_dataset: str
    split_strategy: str
    evaluation_status: str
    external_validation: bool
    architecture: str = "unknown"
    metadata_dim: int = 0
    input_mode: str = "fusion"
    supported_countries: frozenset[str] = frozenset()
    thresholds: Mapping[str, float] = field(
        default_factory=lambda: {"elevated": 0.35, "higher": 0.65}
    )
    preprocessing: Mapping[str, Any] = field(default_factory=dict)
    calibration_status: str = "unknown"

def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactManifestError(f"{field} is required")
    return value.strip()


def _parse_sha256(payload: dict[str, Any]) -> str:
    digest = _required_string(payload, "artifact_sha256").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ArtifactManifestError("artifact_sha256 must be a SHA-256 digest")
    return digest


def _parse_runtime_fields(payload: dict[str, Any]) -> dict[str, Any]:
    metadata_dim = payload.get("metadata_dim", 0)
    if isinstance(metadata_dim, bool) or not isinstance(metadata_dim, int):
        raise ArtifactManifestError("metadata_dim must be an integer")
    input_mode = payload.get("input_mode", "fusion")
    if input_mode not in {"audio", "clinical", "fusion"}:
        raise ArtifactManifestError("input_mode must be audio, clinical, or fusion")
    countries = payload.get("supported_countries", [])
    if not isinstance(countries, list) or not all(isinstance(country, str) for country in countries):
        raise ArtifactManifestError("supported_countries must be a list of strings")
    thresholds = payload.get("thresholds", {"elevated": 0.35, "higher": 0.65})
    if (
        not isinstance(thresholds, dict)
        or not isinstance(thresholds.get("elevated"), (int, float))
        or not isinstance(thresholds.get("higher"), (int, float))
        or not 0.0 < float(thresholds["elevated"]) < float(thresholds["higher"]) < 1.0
    ):
        raise ArtifactManifestError("thresholds must contain ordered elevated and higher values")
    preprocessing = payload.get("preprocessing", {})
    if not isinstance(preprocessing, dict):
        raise ArtifactManifestError("preprocessing must be an object")
    return {
        "architecture": str(payload.get("architecture", "unknown")),
        "metadata_dim": metadata_dim,
        "input_mode": input_mode,
        "supported_countries": frozenset(country.strip().upper() for country in countries),
        "thresholds": {
            "elevated": float(thresholds["elevated"]),
            "higher": float(thresholds["higher"]),
        },
        "preprocessing": preprocessing,
        "calibration_status": str(payload.get("calibration_status", "unknown")),
    }


def load_artifact_manifest(path: str | Path) -> ArtifactManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactManifestError("manifest must be readable JSON") from error
    if not isinstance(payload, dict):
        raise ArtifactManifestError("manifest must be a JSON object")

    gate = payload.get("evaluation_gate")
    if not isinstance(gate, dict) or gate.get("status") != "passed":
        raise ArtifactManifestError("evaluation gate must be explicitly passed")
    if gate.get("external_validation") is not True:
        raise ArtifactManifestError("external validation is required")

    runtime_fields = _parse_runtime_fields(payload)
    split_strategy = _required_string(payload, "split_strategy")
    if split_strategy != "patient_grouped":
        raise ArtifactManifestError("split_strategy must be patient_grouped")

    return ArtifactManifest(
        model_name=_required_string(payload, "model_name"),
        model_version=_required_string(payload, "model_version"),
        artifact_path=_required_string(payload, "artifact_path"),
        artifact_sha256=_parse_sha256(payload),
        training_dataset=_required_string(payload, "training_dataset"),
        split_strategy=split_strategy,
        evaluation_status="passed",
        external_validation=True,
        **runtime_fields,
    )


def verify_artifact_digest(artifact_path: str | Path, expected_sha256: str) -> None:
    """Verify model bytes before loading them into the inference process."""
    digest = hashlib.sha256()
    try:
        with Path(artifact_path).open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ArtifactManifestError("model artifact is not readable") from error
    if digest.hexdigest() != expected_sha256.lower():
        raise ArtifactManifestError("model artifact checksum does not match manifest")
