from __future__ import annotations

import pytest

from training.metrics import calculate_binary_metrics, select_threshold


def test_metrics_report_perfect_ranked_predictions() -> None:
    metrics = calculate_binary_metrics([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])

    assert metrics["auroc"] == pytest.approx(1.0)
    assert metrics["average_precision"] == pytest.approx(1.0)
    assert metrics["brier_score"] < 0.05


def test_metrics_report_missing_auroc_when_only_one_class_exists() -> None:
    metrics = calculate_binary_metrics([1, 1], [0.7, 0.8])

    assert metrics["auroc"] is None
    assert metrics["positive_count"] == 2


def test_threshold_selection_uses_validation_labels_and_scores() -> None:
    threshold = select_threshold([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])

    assert 0.4 < threshold <= 0.6
