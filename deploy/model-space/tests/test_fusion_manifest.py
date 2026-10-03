"""Manifest gate for the fusion candidate (residual_fusion_cnn_v3).

These tests exist to make specific claims impossible to fake. The project
advertises a from-scratch student on a public-facing transparency page, so
the manifest has to actively refuse the combination that would make that
claim false.
"""

from __future__ import annotations

import json

import pytest

from training.pipeline import build_candidate_manifest


ARCHITECTURE = "residual_fusion_cnn_v3"
METADATA_DIM = 27


def _preprocessing() -> dict:
    from src.audio_features import AudioFeatureConfig
    from training.encoding import CLINICAL_FEATURE_ORDER

    return {
        "audio": AudioFeatureConfig.tb_screen_reference().to_manifest(),
        "clinical": {
            "clinical_feature_order": list(CLINICAL_FEATURE_ORDER),
            "numeric_stats": {
                "age": {"mean": 40.0, "std": 15.0},
                "height": {"mean": 165.0, "std": 9.0},
                "weight": {"mean": 60.0, "std": 12.0},
                "reported_cough_dur": {"mean": 30.0, "std": 20.0},
                "heart_rate": {"mean": 85.0, "std": 12.0},
                "temperature": {"mean": 37.2, "std": 0.4},
            },
        },
    }


def _write(tmp_path) -> "object":
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fusion candidate")
    return artifact


def _build(tmp_path, **overrides):
    kwargs = {
        "model_name": "fusion",
        "model_version": "4.0.0-research-candidate",
        "input_mode": "fusion",
        "metadata_dim": METADATA_DIM,
        "supported_countries": ["PH", "ZA"],
        "preprocessing": _preprocessing(),
        "evaluation": {"test": {"auroc": 0.82}},
        "thresholds": {"elevated": 0.4, "higher": 0.7},
        "training_dataset": "CODA-TB",
        "architecture": ARCHITECTURE,
        "initialization": "random_pytorch_default",
        "pretrained_weights": False,
        "seed": 7,
    }
    kwargs.update(overrides)
    return build_candidate_manifest(_write(tmp_path), tmp_path / "manifest.json", **kwargs)


def test_valid_fusion_manifest_is_accepted(tmp_path) -> None:
    path = _build(tmp_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["architecture"] == ARCHITECTURE
    assert manifest["pretrained_weights"] is False
    assert manifest["initialization"] == "random_pytorch_default"
    assert manifest["split_strategy"] == "patient_grouped"
    assert manifest["evaluation_gate"] == {"status": "blocked", "external_validation": False}


def test_fusion_cannot_claim_pretrained_weights(tmp_path) -> None:
    """A pretrained student would break the from-scratch claim entirely."""
    with pytest.raises(ValueError, match="reject pretrained weights"):
        _build(tmp_path, pretrained_weights=True)


def test_fusion_must_declare_random_initialisation(tmp_path) -> None:
    with pytest.raises(ValueError, match="declare random initialization"):
        _build(tmp_path, initialization="pretrained_finetune")


def test_fusion_requires_fusion_input_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="requires fusion input"):
        _build(tmp_path, input_mode="audio")


def test_fusion_requires_positive_metadata_dim(tmp_path) -> None:
    with pytest.raises(ValueError, match="requires fusion input"):
        _build(tmp_path, metadata_dim=0)


def test_fusion_requires_declared_clinical_feature_order(tmp_path) -> None:
    preprocessing = _preprocessing()
    preprocessing["clinical"]["clinical_feature_order"] = [
        "sex",
        "age",
    ]
    with pytest.raises(ValueError, match="clinical_feature_order length"):
        _build(tmp_path, preprocessing=preprocessing)


def test_fusion_requires_numeric_stats_object(tmp_path) -> None:
    preprocessing = _preprocessing()
    preprocessing["clinical"]["numeric_stats"] = ["age", "height"]
    with pytest.raises(ValueError, match="numeric_stats must be an object"):
        _build(tmp_path, preprocessing=preprocessing)


def test_fusion_requires_numeric_stats_covering_every_numeric_field(tmp_path) -> None:
    """Normalisation constants are what the preprocessor applied. If a field is
    missing, the served vector silently disagrees with the trained one."""
    preprocessing = _preprocessing()
    del preprocessing["clinical"]["numeric_stats"]["temperature"]
    with pytest.raises(ValueError, match="numeric_stats"):
        _build(tmp_path, preprocessing=preprocessing)


# ── Distillation disclosure ─────────────────────────────────────────────────


def test_distillation_is_recorded_when_used(tmp_path) -> None:
    path = _build(
        tmp_path,
        distillation={"teacher_model_id": "facebook/ast-finetuned-audioset-10-10-0.97", "weight": 0.3},
    )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["distillation"]["teacher_model_id"].startswith("facebook/ast")
    assert manifest["distillation"]["weight"] == 0.3
    # Distillation shapes gradients during training only; the artifact itself
    # is still the from-scratch student.
    assert manifest["pretrained_weights"] is False


def test_distillation_without_teacher_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="teacher_model_id"):
        _build(tmp_path, distillation={"weight": 0.3})


def test_distillation_with_blank_teacher_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="teacher_model_id"):
        _build(tmp_path, distillation={"teacher_model_id": "   ", "weight": 0.3})


@pytest.mark.parametrize("weight", [0, 1, 1.2, -0.5, "0.3", None])
def test_distillation_weight_must_be_strictly_inside_the_unit_interval(
    tmp_path, weight
) -> None:
    with pytest.raises(ValueError, match="weight must be a number strictly between 0 and 1"):
        _build(
            tmp_path,
            distillation={"teacher_model_id": "facebook/ast-finetuned-audioset-10-10-0.97", "weight": weight},
        )


def test_absent_distillation_field_defaults_to_empty(tmp_path) -> None:
    manifest = json.loads(_build(tmp_path).read_text(encoding="utf-8"))
    assert manifest["distillation"] == {}


def test_empty_distillation_dict_is_treated_as_absent(tmp_path) -> None:
    manifest = json.loads(_build(tmp_path, distillation={}).read_text(encoding="utf-8"))
    assert manifest["distillation"] == {}


# ── Gate evaluasi ───────────────────────────────────────────────────────────


def test_fusion_candidate_stays_blocked_without_external_validation(tmp_path) -> None:
    manifest = json.loads(_build(tmp_path).read_text(encoding="utf-8"))
    assert manifest["evaluation_gate"]["status"] == "blocked"
    assert manifest["evaluation_gate"]["external_validation"] is False


def test_south_africa_is_accepted_as_a_supported_country(tmp_path) -> None:
    manifest = json.loads(
        _build(tmp_path, supported_countries=["ZA", "PH"]).read_text(encoding="utf-8")
    )
    assert "ZA" in manifest["supported_countries"]
    assert "SA" not in manifest["supported_countries"]
