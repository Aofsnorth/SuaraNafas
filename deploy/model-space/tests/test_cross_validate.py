from __future__ import annotations

import numpy as np
import pytest
import torch

import training.cross_validate as cross_validate
from training.cross_validate import (
    FitResult,
    _aggregate_operating_points,
    _selected_epoch,
)
from training.dataset import PatientExample
from training.evaluator import EvaluationResult
from training.metrics import calculate_binary_metrics
from training.train import PreparedPatient


def test_selected_epoch_uses_median_inner_selection() -> None:
    assert _selected_epoch([3, 7, 9, 11]) == 8
    assert _selected_epoch([2, 8, 5]) == 5

    with pytest.raises(ValueError, match="positive"):
        _selected_epoch([0, 1])


def test_aggregate_operating_points_pools_confusion_counts() -> None:
    aggregated = _aggregate_operating_points(
        [
            {"tp": 8, "tn": 3, "fp": 2, "fn": 1},
            {"tp": 7, "tn": 4, "fp": 1, "fn": 2},
        ]
    )

    assert aggregated == {
        "sample_count": 28,
        "positive_count": 18,
        "negative_count": 10,
        "tp": 15,
        "tn": 7,
        "fp": 3,
        "fn": 3,
        "sensitivity": 15 / 18,
        "specificity": 0.7,
        "false_negative_rate": 3 / 18,
        "false_positive_rate": 0.3,
    }


def test_nested_runner_never_sends_outer_test_records_to_inner_fit(
    tmp_path,
    monkeypatch,
) -> None:
    folds = tuple(
        tuple(
            PatientExample(
                patient_id=f"fold-{fold_index}-class-{label}",
                label=label,
                audio_paths=(),
                metadata={},
            )
            for label in (0, 1)
        )
        for fold_index in range(3)
    )
    fit_calls: list[tuple[set[str], set[str]]] = []

    def fake_prepare(records, audio_config, *, partition_name):
        del audio_config, partition_name
        return tuple(
            PreparedPatient(
                record.patient_id,
                record.label,
                np.zeros((1, 1, 64, 101), dtype=np.float32),
            )
            for record in records
        )

    def fake_fit(train_records, validation_records, **kwargs):
        del kwargs
        fit_calls.append(
            (
                {record.patient_id for record in train_records},
                {record.patient_id for record in validation_records},
            )
        )
        labels = tuple(record.label for record in validation_records)
        probabilities = tuple(0.8 if label else 0.2 for label in labels)
        return FitResult(
            state_dict={},
            best_epoch=1,
            validation=EvaluationResult(
                labels,
                probabilities,
                calculate_binary_metrics(labels, probabilities),
            ),
        )

    def fake_refit(*args, **kwargs):
        del args, kwargs
        return torch.nn.Linear(1, 1)

    def fake_evaluate(*args, **kwargs):
        del args, kwargs
        labels = (0, 1)
        probabilities = (0.2, 0.8)
        return EvaluationResult(
            labels,
            probabilities,
            calculate_binary_metrics(labels, probabilities),
        )

    monkeypatch.setattr(cross_validate, "_prepare_examples", fake_prepare)
    monkeypatch.setattr(cross_validate, "_fit_with_validation", fake_fit)
    monkeypatch.setattr(cross_validate, "_fit_fixed_epochs", fake_refit)
    monkeypatch.setattr(cross_validate, "_evaluate", fake_evaluate)

    manifest_path = cross_validate.run_nested_cross_validation(
        folds,
        fold_hashes=("a" * 64, "b" * 64, "c" * 64),
        output_dir=tmp_path,
        epochs=1,
        batch_size=2,
        seed=42,
        device=torch.device("cpu"),
        elevated_sensitivity=1.0,
        higher_sensitivity=0.8,
        use_augmentation=False,
        excluded_subjects=(),
    )

    all_ids = {record.patient_id for fold in folds for record in fold}
    assert manifest_path.exists()
    assert len(fit_calls) == 6
    for train_ids, validation_ids in fit_calls:
        outer_test_ids = all_ids - train_ids - validation_ids
        assert train_ids.isdisjoint(validation_ids)
        assert len(train_ids) == 2
        assert len(validation_ids) == 2
        assert len(outer_test_ids) == 2
