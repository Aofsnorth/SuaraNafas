from __future__ import annotations

import hashlib
import json

import pytest
import torch

from src.audio_features import AudioFeatureConfig
from src.model import (
    RESIDUAL_SPECTROGRAM_CNN_V2,
    SPECTROGRAM_AUDIO_CNN_V1,
    SPECTROGRAM_CLINICAL_BASELINE_V1,
    SpectrogramClinicalClassifier,
    build_screening_model,
)
from src.model_runtime import ModelConfigurationError, load_torch_screening_model


def write_manifest(
    tmp_path,
    *,
    gate_status="passed",
    external_validation=True,
    input_mode="fusion",
    target_frames=36,
    architecture=None,
):
    artifact_path = tmp_path / "model.pt"
    metadata_dim = 27 if input_mode == "fusion" else 0
    architecture = architecture or (
        SPECTROGRAM_CLINICAL_BASELINE_V1
        if input_mode == "fusion"
        else SPECTROGRAM_AUDIO_CNN_V1
    )
    feature_config = (
        AudioFeatureConfig.tb_screen_reference()
        if architecture == RESIDUAL_SPECTROGRAM_CNN_V2
        else AudioFeatureConfig(duration_seconds=0.55, target_frames=target_frames)
    )
    model = build_screening_model(
        architecture,
        metadata_dim=metadata_dim,
        input_mode=input_mode,
        expected_n_mels=feature_config.n_mels,
        expected_target_frames=feature_config.target_frames,
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
        "architecture": architecture,
        "initialization": "random_pytorch_default",
        "pretrained_weights": False,
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
            "audio": feature_config.to_manifest(),
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


def test_loader_accepts_residual_candidate_with_complete_provenance(tmp_path) -> None:
    manifest_path = write_manifest(
        tmp_path,
        gate_status="blocked",
        external_validation=False,
        input_mode="audio",
        architecture=RESIDUAL_SPECTROGRAM_CNN_V2,
    )

    model = load_torch_screening_model(
        manifest_path,
        allow_blocked_candidate=True,
    )

    assert model.is_available is True
    assert model._feature_config == AudioFeatureConfig.tb_screen_reference()
    assert sum(parameter.numel() for parameter in model._model.parameters()) == 307_762


def test_loader_rejects_v1_checkpoint_labelled_as_residual(tmp_path) -> None:
    manifest_path = write_manifest(
        tmp_path,
        input_mode="audio",
        architecture=RESIDUAL_SPECTROGRAM_CNN_V2,
    )
    artifact_path = tmp_path / "model.pt"
    legacy = SpectrogramClinicalClassifier(metadata_dim=0, input_mode="audio")
    torch.save(legacy.state_dict(), artifact_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["artifact_sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelConfigurationError, match="could not be loaded"):
        load_torch_screening_model(manifest_path)


def test_loader_rejects_incomplete_residual_preprocessing(tmp_path) -> None:
    manifest_path = write_manifest(
        tmp_path,
        input_mode="audio",
        architecture=RESIDUAL_SPECTROGRAM_CNN_V2,
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    del payload["preprocessing"]["audio"]["win_length"]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelConfigurationError, match="win_length"):
        load_torch_screening_model(manifest_path)


def test_loader_verifies_artifact_and_loads_validated_model(tmp_path) -> None:
    manifest_path = write_manifest(tmp_path)

    model = load_torch_screening_model(manifest_path)

    assert model.is_available is True
    assert model.supported_countries == frozenset({"PH"})
    assert model.deployment_status == "validated"


@pytest.mark.parametrize("target_frames", [36, 91])
def test_loader_accepts_validated_audio_only_model(tmp_path, target_frames) -> None:
    manifest_path = write_manifest(
        tmp_path,
        input_mode="audio",
        target_frames=target_frames,
    )

    model = load_torch_screening_model(manifest_path)

    assert model.is_available is True
    assert model._feature_config.target_frames == target_frames
    assert model._model.expected_target_frames == target_frames
