from __future__ import annotations

import torch

from src.model import SpectrogramClinicalClassifier


def test_audio_model_accepts_masked_variable_clip_batches() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="audio")
    clips = torch.randn(2, 3, 1, 128, 36)
    mask = torch.tensor([[True, True, False], [True, False, False]])

    logits = model(clips, metadata=None, clip_mask=mask)

    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()


def test_clinical_model_does_not_require_audio() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="clinical")

    logits = model(clips=None, metadata=torch.randn(2, 27))

    assert logits.shape == (2, 2)


def test_fusion_model_requires_both_modalities() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="fusion")

    try:
        model(clips=None, metadata=torch.randn(1, 27))
    except ValueError as error:
        assert "clips" in str(error)
    else:
        raise AssertionError("Fusion model must require audio clips")
