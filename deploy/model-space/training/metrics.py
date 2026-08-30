from __future__ import annotations

from collections.abc import Sequence
from math import isfinite


MetricValue = float | int | None


def _validate_inputs(labels: Sequence[int], probabilities: Sequence[float]) -> None:
    if len(labels) == 0 or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must be non-empty and equally sized")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only 0 and 1")
    if any(not isfinite(float(probability)) or not 0.0 <= probability <= 1.0 for probability in probabilities):
        raise ValueError("probabilities must be finite values between 0 and 1")


def _roc_auc(labels: Sequence[int], probabilities: Sequence[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None

    concordant = 0.0
    positive_scores = [probabilities[index] for index, label in enumerate(labels) if label == 1]
    negative_scores = [probabilities[index] for index, label in enumerate(labels) if label == 0]
    for positive in positive_scores:
        for negative in negative_scores:
            if positive > negative:
                concordant += 1.0
            elif positive == negative:
                concordant += 0.5
    return concordant / (positives * negatives)


def _average_precision(labels: Sequence[int], probabilities: Sequence[float]) -> float | None:
    positives = sum(labels)
    if positives == 0:
        return None

    ranked = sorted(
        zip(probabilities, labels),
        key=lambda item: item[0],
        reverse=True,
    )
    hits = 0
    precision_sum = 0.0
    for rank, (_, label) in enumerate(ranked, start=1):
        if label == 1:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / positives


def calculate_binary_metrics(
    labels: Sequence[int],
    probabilities: Sequence[float],
    threshold: float = 0.5,
) -> dict[str, MetricValue]:
    """Calculate threshold-free and threshold-dependent binary metrics."""
    _validate_inputs(labels, probabilities)
    if not isfinite(float(threshold)) or not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be a finite value between 0 and 1")

    predictions = [probability >= threshold for probability in probabilities]
    true_positive = sum(label == 1 and prediction for label, prediction in zip(labels, predictions))
    true_negative = sum(label == 0 and not prediction for label, prediction in zip(labels, predictions))
    false_positive = sum(label == 0 and prediction for label, prediction in zip(labels, predictions))
    false_negative = sum(label == 1 and not prediction for label, prediction in zip(labels, predictions))
    positive_count = true_positive + false_negative
    negative_count = true_negative + false_positive
    predicted_positive_count = true_positive + false_positive
    predicted_negative_count = true_negative + false_negative
    sensitivity = true_positive / positive_count if positive_count else None
    specificity = true_negative / negative_count if negative_count else None

    brier_score = sum(
        (float(probability) - label) ** 2
        for label, probability in zip(labels, probabilities)
    ) / len(labels)
    return {
        "auroc": _roc_auc(labels, probabilities),
        "average_precision": _average_precision(labels, probabilities),
        "brier_score": brier_score,
        "sample_count": len(labels),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "threshold": float(threshold),
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "tp": true_positive,
        "tn": true_negative,
        "fp": false_positive,
        "fn": false_negative,
        "sensitivity": sensitivity,
        "recall": sensitivity,
        "specificity": specificity,
        "false_negative_rate": false_negative / positive_count if positive_count else None,
        "false_positive_rate": false_positive / negative_count if negative_count else None,
        "fnr": false_negative / positive_count if positive_count else None,
        "fpr": false_positive / negative_count if negative_count else None,
        "precision": true_positive / predicted_positive_count if predicted_positive_count else None,
        "negative_predictive_value": (
            true_negative / predicted_negative_count if predicted_negative_count else None
        ),
        "npv": true_negative / predicted_negative_count if predicted_negative_count else None,
    }


def select_threshold_for_minimum_sensitivity(
    labels: Sequence[int],
    probabilities: Sequence[float],
    minimum_sensitivity: float,
) -> float:
    """Select the most specific validation threshold meeting a sensitivity target."""
    _validate_inputs(labels, probabilities)
    if not isfinite(float(minimum_sensitivity)) or not 0.0 < minimum_sensitivity <= 1.0:
        raise ValueError("minimum_sensitivity must be a finite value in (0, 1]")
    if len(set(labels)) < 2:
        return 0.5

    positive_count = sum(labels)
    candidates = sorted(set(float(probability) for probability in probabilities), reverse=True)
    for threshold in candidates:
        true_positive = sum(
            label == 1 and probability >= threshold
            for label, probability in zip(labels, probabilities)
        )
        if true_positive / positive_count >= minimum_sensitivity:
            return threshold

    raise RuntimeError("no threshold satisfies minimum_sensitivity")


def select_threshold(labels: Sequence[int], probabilities: Sequence[float]) -> float:
    """Select a validation-only threshold using Youden's J statistic."""
    _validate_inputs(labels, probabilities)
    if len(set(labels)) < 2:
        return 0.5

    candidates = sorted(set(float(probability) for probability in probabilities))
    best_threshold = candidates[0]
    best_score = float("-inf")
    for threshold in candidates:
        predicted = [probability >= threshold for probability in probabilities]
        true_positive = sum(label == 1 and prediction for label, prediction in zip(labels, predicted))
        false_positive = sum(label == 0 and prediction for label, prediction in zip(labels, predicted))
        positive_count = sum(labels)
        negative_count = len(labels) - positive_count
        youden_j = true_positive / positive_count - false_positive / negative_count
        if youden_j > best_score or (youden_j == best_score and threshold > best_threshold):
            best_score = youden_j
            best_threshold = threshold
    return best_threshold
