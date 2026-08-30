from __future__ import annotations

import pytest

from training.metrics import (
    calculate_binary_metrics,
    select_threshold,
    select_threshold_for_minimum_sensitivity,
)
from training.train import _ordered_thresholds


def test_metrics_include_patient_level_counts() -> None:
    metrics = calculate_binary_metrics([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8])

    assert metrics["sample_count"] == 4
    assert metrics["positive_count"] == 2
    assert metrics["negative_count"] == 2
    assert metrics["auroc"] == 1.0


def test_threshold_selection_is_deterministic() -> None:
    assert select_threshold([0, 1], [0.1, 0.9]) == 0.9


def test_metrics_include_threshold_dependent_confusion_rates() -> None:
    metrics = calculate_binary_metrics(
        [1, 1, 0, 0],
        [0.9, 0.4, 0.7, 0.1],
        threshold=0.5,
    )

    assert metrics["tp"] == metrics["true_positive"] == 1
    assert metrics["tn"] == metrics["true_negative"] == 1
    assert metrics["fp"] == metrics["false_positive"] == 1
    assert metrics["fn"] == metrics["false_negative"] == 1
    assert metrics["sensitivity"] == metrics["recall"] == 0.5
    assert metrics["specificity"] == 0.5
    assert metrics["fnr"] == metrics["false_negative_rate"] == 0.5
    assert metrics["fpr"] == metrics["false_positive_rate"] == 0.5
    assert metrics["precision"] == 0.5
    assert metrics["npv"] == metrics["negative_predictive_value"] == 0.5


def test_metrics_report_undefined_rates_when_denominators_are_empty() -> None:
    all_positive = calculate_binary_metrics([1, 1], [0.8, 0.9])
    no_predicted_positive = calculate_binary_metrics([0, 1], [0.1, 0.2])

    assert all_positive["specificity"] is None
    assert all_positive["false_positive_rate"] is None
    assert all_positive["negative_predictive_value"] is None
    assert no_predicted_positive["precision"] is None


def test_minimum_sensitivity_selects_highest_qualifying_threshold() -> None:
    threshold = select_threshold_for_minimum_sensitivity(
        [1, 1, 0, 0],
        [0.9, 0.6, 0.8, 0.2],
        minimum_sensitivity=1.0,
    )

    assert threshold == 0.6


def test_equal_risk_thresholds_preserve_selected_sensitivity_boundary() -> None:
    thresholds = _ordered_thresholds(0.5, 0.5)
    metrics = calculate_binary_metrics([1, 0], [0.5, 0.1], thresholds["higher"])

    assert thresholds == {"elevated": 0.5, "higher": 0.5}
    assert metrics["sensitivity"] == 1.0


def test_minimum_sensitivity_selection_is_deterministic_for_tied_scores() -> None:
    threshold = select_threshold_for_minimum_sensitivity(
        [1, 1, 0, 0],
        [0.7, 0.7, 0.7, 0.1],
        minimum_sensitivity=0.5,
    )

    assert threshold == 0.7


@pytest.mark.parametrize("minimum_sensitivity", [0.0, -0.1, 1.1, float("nan")])
def test_minimum_sensitivity_rejects_invalid_target(minimum_sensitivity: float) -> None:
    with pytest.raises(ValueError, match="minimum_sensitivity"):
        select_threshold_for_minimum_sensitivity(
            [0, 1],
            [0.1, 0.9],
            minimum_sensitivity,
        )


@pytest.mark.parametrize("labels", [[0, 0], [1, 1]])
def test_minimum_sensitivity_handles_one_class_labels(labels: list[int]) -> None:
    assert select_threshold_for_minimum_sensitivity(labels, [0.2, 0.8], 0.8) == 0.5
