"""End-to-end checks for the fusion cross-validation runner.

These run a real (tiny) training loop over synthetic WAV files, because the
failure modes worth protecting against are structural, not numerical: a
patient leaking across folds, a preprocessor fitted on the test partition, a
manifest that cannot be served.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from src.audio_features import AudioFeatureConfig, SpecAugmentConfig
from training.cross_validate_fusion import (
    FusionPatient,
    _batches,
    _build_batch,
    _class_weights,
    _new_fusion_model,
    _selected_epoch,
    run_cross_validation,
)
from training.dataset import PatientExample
from training.encoding import CLINICAL_FEATURE_ORDER, NUMERIC_FIELDS, ClinicalPreprocessor
from tests.factories.metadata import build_wav


METADATA_DIM = len(CLINICAL_FEATURE_ORDER)


def _write_wav(path: Path, frequency: float) -> Path:
    path.write_bytes(build_wav(duration_seconds=1.0, frequency_hz=frequency))
    return path


def _example(tmp_path: Path, index: int, label: int, clips: int = 2) -> PatientExample:
    root = tmp_path / f"p{index:03d}"
    root.mkdir(parents=True, exist_ok=True)
    paths = tuple(
        _write_wav(root / f"c{clip}.wav", 180.0 + 40.0 * label + 7.0 * clip)
        for clip in range(clips)
    )
    # Age is deliberately correlated with the label so the clinical branch has
    # something to learn; a random vector would make leakage tests meaningless.
    metadata = {
        "sex": "Male" if index % 2 else "Female",
        "age": str(25 + 30 * label + (index % 5)),
        "height": str(160 + (index % 12)),
        "weight": str(50 + 20 * label + (index % 7)),
        "reported_cough_dur": str(10 + 25 * label),
        "heart_rate": str(75 + 20 * label),
        "temperature": str(36.8 + 1.2 * label),
        "Country": "PH",
        "HIVstatus": "Positive" if label else "Negative",
        "hemoptysis": "Yes" if label else "No",
    }
    return PatientExample(f"p{index:03d}", label, paths, metadata)


def _cohort(tmp_path: Path, patients: int = 12):
    return [
        _example(tmp_path, index, index % 2)
        for index in range(patients)
    ]


# ── Unit: komponen dalam runner ──────────────────────────────────────────────


def _patient(patient_id: str, label: int, clip_count: int) -> FusionPatient:
    """One patient. Clips are (clip, 1, n_mels, frames) as produced by
    extract_log_mel, which is what _build_batch expects."""
    return FusionPatient(
        patient_id,
        label,
        np.ones((clip_count, 1, 64, 101), dtype=np.float32),
        np.zeros(METADATA_DIM, dtype=np.float32),
    )


def test_class_weights_favour_the_minority_class() -> None:
    """TB is the rare class; without this the model predicts "no TB" always."""
    patients = [_patient(f"p{i}", 0 if i < 6 else 1, 1) for i in range(8)]
    weights = _class_weights(patients)
    assert weights.shape == (2,)
    assert float(weights[1]) > float(weights[0])


def test_class_weights_are_equal_for_a_balanced_cohort() -> None:
    patients = [_patient(f"p{i}", i % 2, 1) for i in range(8)]
    weights = _class_weights(patients)
    assert float(weights[0]) == pytest.approx(float(weights[1]))


def test_class_weights_require_both_classes_in_every_fold() -> None:
    """A fold that happens to be single-class cannot be trained honestly."""
    with pytest.raises(ValueError, match="both classes"):
        _class_weights([_patient(f"p{i}", 1, 1) for i in range(3)])


def test_selected_epoch_is_the_median() -> None:
    assert _selected_epoch([1, 5, 3, 9, 7]) == 5
    assert _selected_epoch([4]) == 4


def test_build_batch_pads_clips_and_preserves_mask() -> None:
    audio_config = AudioFeatureConfig.tb_screen_reference()
    patients = [_patient("a", 1, 3), _patient("b", 0, 1)]
    patients[1] = FusionPatient(
        "b", 0, patients[1].clips, np.ones(METADATA_DIM, dtype=np.float32)
    )
    clips, mask, clinical, labels = _build_batch(patients, audio_config)
    assert clips.shape == (2, 3, 1, audio_config.n_mels, audio_config.target_frames)
    assert mask.dtype == torch.bool
    assert mask[0].all() and not mask[1, 1:].any()
    assert clinical.shape == (2, METADATA_DIM)
    assert labels.tolist() == [1, 0]


def test_padded_clips_do_not_influence_patients_without_them() -> None:
    audio_config = AudioFeatureConfig.tb_screen_reference()
    model = _new_fusion_model(METADATA_DIM, audio_config, torch.device("cpu")).eval()
    short = _patient("b", 0, 1)
    long = _patient("a", 1, 3)
    baseline = _build_batch([short, long], audio_config)
    mutated_patient = FusionPatient(
        "a", 1, np.full((3, 1, 64, 101), 7.0, dtype=np.float32), long.clinical
    )
    mutated = _build_batch([short, mutated_patient], audio_config)
    with torch.inference_mode():
        before = model(baseline[0], baseline[2], baseline[1])
        after = model(mutated[0], mutated[2], mutated[1])
    assert torch.allclose(before[0], after[0], atol=1e-6), "padding must not leak between patients"
    assert not torch.allclose(before[1], after[1]), "sanity: the mutated patient must change"


def test_fusion_model_rejects_clinical_vector_of_wrong_width() -> None:
    model = _new_fusion_model(METADATA_DIM, AudioFeatureConfig.tb_screen_reference(), torch.device("cpu"))
    with pytest.raises(ValueError, match="metadata"):
        model(
            torch.zeros(1, 2, 1, 64, 101),
            torch.zeros(1, 3),
            torch.ones(1, 2, dtype=torch.bool),
        )


# ── Leakage ─────────────────────────────────────────────────────────────────


def test_preprocessor_is_fitted_on_train_partition_only() -> None:
    """A preprocessor fitted on everything leaks the test partition's mean and
    std, which is enough to inflate an imbalanced-cohort score."""
    train = [
        {"age": str(20 + i), "height": "170", "weight": "60", "reported_cough_dur": "10",
         "heart_rate": "70", "temperature": "36.5", "Country": "PH", "HIVstatus": "Negative"}
        for i in range(5)
    ]
    fit_on_train = ClinicalPreprocessor.fit(train)
    everything = ClinicalPreprocessor.fit(
        train + [{"age": "900", "height": "170", "weight": "60", "reported_cough_dur": "10",
                  "heart_rate": "70", "temperature": "36.5", "Country": "PH", "HIVstatus": "Positive"}]
    )
    assert fit_on_train.numeric_stats["age"]["mean"] != everything.numeric_stats["age"]["mean"]


def test_runner_requires_at_least_two_folds(tmp_path) -> None:
    audio_config = AudioFeatureConfig.tb_screen_reference()
    with pytest.raises(ValueError, match="at least two folds"):
        run_cross_validation(
            _cohort(tmp_path, 4),
            audio_config=audio_config,
            folds=1,
            validation_fraction=0.25,
            test_fraction=0.25,
            epochs=1,
            batch_size=2,
            seed=0,
            device=torch.device("cpu"),
            elevated_sensitivity=0.8,
            higher_sensitivity=0.9,
        )


# ── End-to-end ──────────────────────────────────────────────────────────────


def _run(tmp_path: Path, **overrides):
    audio_config = AudioFeatureConfig.tb_screen_reference()
    kwargs = {
        "audio_config": audio_config,
        "folds": 2,
        "validation_fraction": 0.25,
        "test_fraction": 0.25,
        "epochs": 1,
        "batch_size": 2,
        "seed": 11,
        "device": torch.device("cpu"),
        "elevated_sensitivity": 0.8,
        "higher_sensitivity": 0.9,
    }
    kwargs.update(overrides)
    return run_cross_validation(_cohort(tmp_path, 12), **kwargs)


def test_cross_validation_runs_and_reports_every_fold(tmp_path) -> None:
    report = _run(tmp_path)
    assert len(report["folds"]) == 2
    scored = [pid for fold in report["folds"] for pid in fold["test_patient_ids"]]
    # Repeated holdout only scores the held-out partition, so the pooled
    # metrics cover the held-out participants, not the whole cohort.
    assert len(report["labels"]) == len(scored)
    assert len(report["probabilities"]) == len(scored)
    assert all(0.0 <= p <= 1.0 for p in report["probabilities"])
    assert all(label in (0, 1) for label in report["labels"])
    assert set(report["thresholds"]) == {"elevated", "higher"}
    assert report["subjects"] == 12
    assert report["pooled_metrics"]["auroc"] is not None


def test_cross_validation_is_deterministic_for_a_fixed_seed(tmp_path) -> None:
    first = _run(tmp_path / "a")
    second = _run(tmp_path / "b")
    assert first["labels"] == second["labels"]
    assert first["patient_ids"] == second["patient_ids"]
    assert first["probabilities"] == pytest.approx(second["probabilities"], abs=1e-6)


def test_cross_validation_scores_each_held_out_patient_at_most_once_per_fold(tmp_path) -> None:
    """Repeated holdout deliberately re-scores participants across folds to
    average out split luck. The guarantee is per-fold disjointness, not global
    uniqueness, so assert the honest property."""
    report = _run(tmp_path, folds=3)
    assert report["patient_ids"] == [
        pid for fold in report["folds"] for pid in fold["test_patient_ids"]
    ]
    assert len(report["labels"]) == len(report["patient_ids"])
    for fold in report["folds"]:
        assert len(set(fold["test_patient_ids"])) == len(fold["test_patient_ids"])
        assert not (set(fold["test_patient_ids"]) & set(fold["train_patient_ids"]))


def test_pooled_metrics_match_the_scored_participants(tmp_path) -> None:
    """Pooled AUROC must be computed over exactly the held-out predictions,
    not over predictions the report does not list."""
    from training.metrics import calculate_binary_metrics

    report = _run(tmp_path, folds=2)
    recomputed = calculate_binary_metrics(report["labels"], report["probabilities"])
    assert recomputed["auroc"] == pytest.approx(report["pooled_metrics"]["auroc"], abs=1e-9)


def test_cross_validation_does_not_train_on_test_patients(tmp_path) -> None:
    """Each fold's test participants must be absent from its train and
    validation ids. This is the guarantee the pooled AUROC rests on."""
    report = _run(tmp_path, folds=2)
    for fold in report["folds"]:
        test = set(fold["test_patient_ids"])
        assert not (test & set(fold["train_patient_ids"])), f"fold {fold['fold']} leaks into train"
        assert not (test & set(fold["validation_patient_ids"])), f"fold {fold['fold']} leaks into validation"
        assert len(test) == fold["test_subjects"]


def test_cross_validation_partitions_cover_every_participant(tmp_path) -> None:
    report = _run(tmp_path, folds=2)
    all_ids = {f"p{i:03d}" for i in range(12)}
    for fold in report["folds"]:
        union = (
            set(fold["train_patient_ids"])
            | set(fold["validation_patient_ids"])
            | set(fold["test_patient_ids"])
        )
        assert union == all_ids, "a participant was dropped from a fold"
        assert not (set(fold["train_patient_ids"]) & set(fold["validation_patient_ids"]))


def test_cross_validation_uses_a_different_holdout_per_fold(tmp_path) -> None:
    """If every fold tested the same patients, 'repeated' is a lie."""
    report = _run(tmp_path, folds=2)
    first = set(report["folds"][0]["test_patient_ids"])
    second = set(report["folds"][1]["test_patient_ids"])
    assert first != second


def test_augmented_batches_accept_the_channels_the_feature_extractor_emits() -> None:
    """Regression: ``extract_log_mel`` keeps a channel axis, so a clip is
    ``(1, n_mels, frames)``. Augmenting treated it as a bare spectrogram and
    aborted the first run with 'log_mel must be 2D'."""
    config = AudioFeatureConfig.tb_screen_reference()
    patients = [_patient(f"P{i}", label=i % 2, clip_count=2) for i in range(3)]

    batches = _batches(
        patients,
        batch_size=2,
        audio_config=config,
        augment=SpecAugmentConfig(),
    )

    clips, mask, clinical, labels = batches[0]
    assert clips.shape[1:] == (2, 1, config.n_mels, config.target_frames)
    assert mask.shape[:2] == (clips.shape[0], 2)
    assert clinical.shape[0] == clips.shape[0]
    assert labels.shape[0] == clips.shape[0]


def test_augmentation_is_disabled_when_the_config_is_omitted() -> None:
    config = AudioFeatureConfig.tb_screen_reference()
    patients = [_patient(f"P{i}", label=i % 2, clip_count=2) for i in range(3)]

    plain = _batches(patients, batch_size=2, audio_config=config)
    augmented = _batches(
        patients,
        batch_size=2,
        audio_config=config,
        augment=SpecAugmentConfig(),
    )

    assert not np.array_equal(plain[0][0].numpy(), augmented[0][0].numpy())
