from __future__ import annotations

import pytest
import torch

from src.model import (
    RESIDUAL_SPECTROGRAM_CNN_V2,
    ResidualSpectrogramClassifier,
    SpectrogramClinicalClassifier,
    build_screening_model,
)


def test_audio_model_accepts_masked_variable_clip_batches() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="audio")
    clips = torch.randn(2, 3, 1, 128, 91)
    mask = torch.tensor([[True, True, False], [True, False, False]])

    logits = model(clips, metadata=None, clip_mask=mask)

    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()


def test_audio_model_accepts_configured_shape_and_rejects_mismatch() -> None:
    model = SpectrogramClinicalClassifier(
        input_mode="audio",
        expected_n_mels=128,
        expected_target_frames=36,
    )

    logits = model(torch.randn(2, 1, 128, 36), metadata=None)

    assert logits.shape == (2, 2)
    with pytest.raises(ValueError, match=r"1, 128, 36"):
        model(torch.randn(2, 1, 128, 91), metadata=None)


def test_residual_model_aggregates_variable_clip_batches() -> None:
    model = ResidualSpectrogramClassifier()
    clips = torch.randn(2, 3, 1, 64, 101)
    mask = torch.tensor([[True, True, False], [True, False, False]])

    logits = model(clips, metadata=None, clip_mask=mask)

    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()
    assert sum(parameter.numel() for parameter in model.parameters()) == 307_762


def test_model_factory_rejects_residual_fusion_and_unknown_architecture() -> None:
    with pytest.raises(ValueError, match="only supports audio"):
        build_screening_model(
            RESIDUAL_SPECTROGRAM_CNN_V2,
            metadata_dim=27,
            input_mode="fusion",
            expected_n_mels=64,
            expected_target_frames=101,
        )
    with pytest.raises(ValueError, match="unsupported"):
        build_screening_model(
            "unknown",
            metadata_dim=0,
            input_mode="audio",
            expected_n_mels=64,
            expected_target_frames=101,
        )


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
