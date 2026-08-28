from __future__ import annotations

from training.metrics import calculate_binary_metrics, select_threshold


def test_metrics_include_patient_level_counts() -> None:
    metrics = calculate_binary_metrics([0, 1, 0, 1], [0.1, 0.9, 0.2, 0.8])

    assert metrics["sample_count"] == 4
    assert metrics["positive_count"] == 2
    assert metrics["negative_count"] == 2
    assert metrics["auroc"] == 1.0


def test_threshold_selection_is_deterministic() -> None:
    assert select_threshold([0, 1], [0.1, 0.9]) == 0.9
