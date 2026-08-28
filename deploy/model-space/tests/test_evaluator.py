from __future__ import annotations

import torch

from src.model import SpectrogramClinicalClassifier
from training.evaluator import evaluate_model


def test_evaluator_returns_patient_level_probabilities() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="fusion")
    clips = torch.randn(4, 2, 1, 128, 36)
    metadata = torch.randn(4, 27)
    labels = torch.tensor([0, 1, 0, 1])

    result = evaluate_model(model, [(clips, metadata, labels)])

    assert len(result.labels) == 4
    assert len(result.probabilities) == 4
    assert all(0.0 <= probability <= 1.0 for probability in result.probabilities)
    assert result.metrics["sample_count"] == 4
