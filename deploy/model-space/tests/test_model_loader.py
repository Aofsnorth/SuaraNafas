from __future__ import annotations

import hashlib
import json

import pytest
import torch

from src.model import SpectrogramClinicalClassifier
from src.model_runtime import ModelConfigurationError, load_torch_screening_model


def write_manifest(
    tmp_path,
    *,
    gate_status="passed",
    external_validation=True,
    input_mode="fusion",
):
    artifact_path = tmp_path / "model.pt"
    metadata_dim = 27 if input_mode == "fusion" else 0
    model = SpectrogramClinicalClassifier(
        metadata_dim=metadata_dim,
        input_mode=input_mode,
    )
    torch.save(model.state_dict(), artifact_path)
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest = {
        "model_name": "test model",
        "model_version": "test-0.1",
        "artifact_path": "model.pt",
        "artifact_sha256": digest,
        "training_dataset": "CODA-TB",
        "split_strategy": "patient_grouped",
        "evaluation_gate": {
            "status": gate_status,
            "external_validation": external_validation,
        },
        "architecture": (
            "spectrogram_clinical_baseline_v1"
            if input_mode == "fusion"
            else "spectrogram_audio_cnn_v1"
        ),
        "metadata_dim": metadata_dim,
        "input_mode": input_mode,
        "supported_countries": ["PH"],
        "thresholds": {"elevated": 0.35, "higher": 0.65},
        "preprocessing": {
            "clinical_feature_order": [
                "sex", "age", "height", "weight", "reported_cough_dur",
                "tb_prior", "tb_prior_Pul", "tb_prior_Extrapul", "tb_prior_Unknown",
                "hemoptysis", "heart_rate", "temperature", "weight_loss",
                "smoke_lweek", "fever", "night_sweats",
                "Numberofcoughsoundscollected", "country_IN", "country_MG",
                "country_PH", "country_SA", "country_TZ", "country_UG",
                "country_VN", "hiv_Negative", "hiv_Positive", "hiv_Unknown",
            ],
            "numeric_stats": {
                field: {"mean": 0.0, "std": 1.0}
                for field in (
                    "age", "height", "weight", "reported_cough_dur",
                    "heart_rate", "temperature",
                )
            },
            "countries": ["IN", "MG", "PH", "SA", "TZ", "UG", "VN"],
            "audio": {
                "sample_rate": 16000,
                "duration_seconds": 0.55,
                "n_mels": 128,
                "n_fft": 1024,
                "hop_length": 256,
                "target_frames": 36,
            },
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_loader_refuses_blocked_candidate_without_explicit_opt_in(tmp_path) -> None:
    manifest_path = write_manifest(
        tmp_path,
        gate_status="blocked",
        external_validation=False,
        input_mode="audio",
    )

    with pytest.raises(ModelConfigurationError, match="evaluation"):
        load_torch_screening_model(manifest_path)


def test_loader_accepts_blocked_candidate_only_with_explicit_opt_in(tmp_path) -> None:
    manifest_path = write_manifest(
        tmp_path,
        gate_status="blocked",
        external_validation=False,
        input_mode="audio",
    )

    model = load_torch_screening_model(
        manifest_path,
        allow_blocked_candidate=True,
    )

    assert model.is_available is True
    assert model.deployment_status == "candidate"


def test_loader_verifies_artifact_and_loads_validated_model(tmp_path) -> None:
    manifest_path = write_manifest(tmp_path)

    model = load_torch_screening_model(manifest_path)

    assert model.is_available is True
    assert model.supported_countries == frozenset({"PH"})
    assert model.deployment_status == "validated"


def test_loader_accepts_validated_audio_only_model(tmp_path) -> None:
    manifest_path = write_manifest(tmp_path, input_mode="audio")

    model = load_torch_screening_model(manifest_path)

    assert model.is_available is True
