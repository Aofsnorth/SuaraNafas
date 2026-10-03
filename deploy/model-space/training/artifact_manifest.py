from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.audio_features import AudioFeatureConfig
from src.model import (
    RESIDUAL_FUSION_CNN_V3,
    RESIDUAL_SPECTROGRAM_CNN_V2,
    RESIDUAL_TABULAR_FUSION_V4,
)


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
    initialization: str = "unspecified"
    pretrained_weights: bool | None = None
    distillation: Mapping[str, Any] = field(default_factory=dict)


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
        or not (
            0.0
            <= float(thresholds["elevated"])
            <= float(thresholds["higher"])
            <= 1.0
        )
    ):
        raise ArtifactManifestError("thresholds must contain ordered elevated and higher values")
    preprocessing = payload.get("preprocessing", {})
    if not isinstance(preprocessing, dict):
        raise ArtifactManifestError("preprocessing must be an object")
    pretrained_weights = payload.get("pretrained_weights")
    if pretrained_weights is not None and not isinstance(pretrained_weights, bool):
        raise ArtifactManifestError("pretrained_weights must be a boolean or null")
    distillation = payload.get("distillation", {})
    if not isinstance(distillation, dict):
        raise ArtifactManifestError("distillation must be an object")
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
        "initialization": str(payload.get("initialization", "unspecified")),
        "pretrained_weights": pretrained_weights,
        "distillation": distillation,
    }


def _validate_numeric_stats(numeric_stats: Mapping[str, Any]) -> None:
    """Every standardised field must ship its normalisation constants.

    A missing entry does not raise at serving time; it just falls back to an
    unstandardised value. The model then receives a vector shifted by roughly
    (x - mean) / std relative to what it was trained on, which shows up as a
    quietly degraded score rather than an error.
    """
    from training.encoding import NUMERIC_FIELDS

    missing = [field for field in NUMERIC_FIELDS if field not in numeric_stats]
    if missing:
        raise ArtifactManifestError(
            "clinical numeric_stats is missing normalisation for: " + ", ".join(missing)
        )
    unexpected = [field for field in numeric_stats if field not in NUMERIC_FIELDS]
    if unexpected:
        raise ArtifactManifestError(
            "clinical numeric_stats names fields the encoder never standardises: "
            + ", ".join(sorted(unexpected))
        )
    for field in NUMERIC_FIELDS:
        stats = numeric_stats[field]
        if not isinstance(stats, Mapping):
            raise ArtifactManifestError(
                f"clinical numeric_stats[{field}] must be an object with mean and std"
            )
        for key in ("mean", "std"):
            value = stats.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ArtifactManifestError(
                    f"clinical numeric_stats[{field}].{key} must be a number"
                )
        if float(stats["std"]) <= 0.0:
            raise ArtifactManifestError(
                f"clinical numeric_stats[{field}].std must be positive"
            )


def _validate_runtime_fields(runtime_fields: Mapping[str, Any]) -> None:
    """Architecture contract shared by the writer and the loader.

    ``build_candidate_manifest`` calls this so a run that produced an
    unservable manifest fails at training time rather than at deploy time,
    after the compute has already been spent.
    """
    architecture = runtime_fields["architecture"]
    residual_architectures = {
        RESIDUAL_SPECTROGRAM_CNN_V2,
        RESIDUAL_FUSION_CNN_V3,
        RESIDUAL_TABULAR_FUSION_V4,
    }
    if architecture in residual_architectures:
        # The *deployed* student stays randomly initialised even when a
        # pretrained teacher guided training. Pretrained weights never reach
        # the artifact, so the manifest must keep declaring them absent.
        if runtime_fields["initialization"] != "random_pytorch_default":
            raise ArtifactManifestError("residual model must declare random initialization")
        if runtime_fields["pretrained_weights"] is not False:
            raise ArtifactManifestError("residual model must explicitly reject pretrained weights")
        audio = runtime_fields["preprocessing"].get("audio")
        if not isinstance(audio, dict):
            raise ArtifactManifestError("residual model requires audio preprocessing")
        try:
            AudioFeatureConfig.from_manifest(audio, strict=True)
        except (TypeError, ValueError) as error:
            raise ArtifactManifestError(str(error)) from error
    if architecture not in (RESIDUAL_FUSION_CNN_V3, RESIDUAL_TABULAR_FUSION_V4):
        return
    if runtime_fields["input_mode"] != "fusion" or runtime_fields["metadata_dim"] < 1:
        raise ArtifactManifestError(
            f"{architecture} requires fusion input with a positive metadata_dim"
        )
    clinical = runtime_fields["preprocessing"].get("clinical")
    if not isinstance(clinical, dict):
        raise ArtifactManifestError("fusion model requires clinical preprocessing")
    feature_order = clinical.get("clinical_feature_order")
    numeric_stats = clinical.get("numeric_stats")
    if not isinstance(feature_order, list) or not feature_order:
        raise ArtifactManifestError("clinical_feature_order must be a non-empty list")
    if not isinstance(numeric_stats, dict):
        raise ArtifactManifestError("clinical numeric_stats must be an object")
    if len(feature_order) != runtime_fields["metadata_dim"]:
        raise ArtifactManifestError(
            "clinical_feature_order length must equal metadata_dim"
        )
    _validate_numeric_stats(numeric_stats)
    distillation = runtime_fields["distillation"]
    if not distillation:
        return
    teacher = distillation.get("teacher_model_id")
    if not isinstance(teacher, str) or not teacher.strip():
        raise ArtifactManifestError(
            "distillation must name the teacher_model_id that guided training"
        )
    weight = distillation.get("weight")
    if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not 0.0 < float(weight) < 1.0:
        raise ArtifactManifestError(
            "distillation weight must be a number strictly between 0 and 1"
        )


def load_artifact_manifest(
    path: str | Path,
    *,
    allow_blocked_candidate: bool = False,
) -> ArtifactManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactManifestError("manifest must be readable JSON") from error
    if not isinstance(payload, dict):
        raise ArtifactManifestError("manifest must be a JSON object")

    gate = payload.get("evaluation_gate")
    if not isinstance(gate, dict):
        raise ArtifactManifestError("evaluation gate must be present")
    evaluation_status = gate.get("status")
    external_validation = gate.get("external_validation") is True
    is_validated = evaluation_status == "passed" and external_validation
    is_candidate = evaluation_status == "blocked" and not external_validation
    if not is_validated and not (allow_blocked_candidate and is_candidate):
        if evaluation_status != "passed":
            raise ArtifactManifestError("evaluation gate must be explicitly passed")
        raise ArtifactManifestError("external validation is required")

    runtime_fields = _parse_runtime_fields(payload)
    _validate_runtime_fields(runtime_fields)
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
        evaluation_status=str(evaluation_status),
        external_validation=external_validation,
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
