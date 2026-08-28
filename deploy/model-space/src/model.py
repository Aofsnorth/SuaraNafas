from __future__ import annotations

import torch
from torch import Tensor, nn


VALID_INPUT_MODES = frozenset({"audio", "clinical", "fusion"})


class SpectrogramEncoder(nn.Module):
    def __init__(self, embedding_dim: int = 32) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.projection = nn.Linear(64, embedding_dim)

    def forward(self, clips: Tensor) -> Tensor:
        return self.projection(self.network(clips).flatten(1))


class ClinicalEncoder(nn.Module):
    def __init__(self, metadata_dim: int, embedding_dim: int = 16) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(metadata_dim, 32),
            nn.ReLU(),
            nn.Linear(32, embedding_dim),
            nn.ReLU(),
        )

    def forward(self, metadata: Tensor) -> Tensor:
        return self.network(metadata)


class SpectrogramClinicalClassifier(nn.Module):
    """Small, reproducible baseline for patient-level research experiments."""

    def __init__(
        self,
        metadata_dim: int = 0,
        *,
        input_mode: str = "fusion",
        audio_embedding_dim: int = 32,
        clinical_embedding_dim: int = 16,
    ) -> None:
        super().__init__()
        if input_mode not in VALID_INPUT_MODES:
            raise ValueError("input_mode must be audio, clinical, or fusion")
        if input_mode in {"clinical", "fusion"} and metadata_dim < 1:
            raise ValueError("metadata_dim must be positive for clinical input")

        self.input_mode = input_mode
        self.audio_encoder = (
            SpectrogramEncoder(audio_embedding_dim)
            if input_mode in {"audio", "fusion"}
            else None
        )
        self.clinical_encoder = (
            ClinicalEncoder(metadata_dim, clinical_embedding_dim)
            if input_mode in {"clinical", "fusion"}
            else None
        )
        representation_dim = {
            "audio": audio_embedding_dim,
            "clinical": clinical_embedding_dim,
            "fusion": audio_embedding_dim + clinical_embedding_dim,
        }[input_mode]
        self.classifier = nn.Sequential(
            nn.Linear(representation_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
        )

    def _encode_audio(self, clips: Tensor, clip_mask: Tensor | None = None) -> Tensor:
        if clips.ndim == 4:
            clips = clips.unsqueeze(1)
        if clips.ndim != 5 or clips.shape[2:] != (1, 128, 36):
            raise ValueError("clips must have shape (batch, clips, 1, 128, 36)")
        batch_size, clip_count = clips.shape[:2]
        if self.audio_encoder is None:
            raise RuntimeError("audio encoder is unavailable for this input mode")
        embeddings = self.audio_encoder(clips.flatten(0, 1))
        embeddings = embeddings.view(batch_size, clip_count, -1)
        if clip_mask is None:
            return embeddings.mean(dim=1)
        if clip_mask.shape != (batch_size, clip_count):
            raise ValueError("clip_mask must match the first two clip dimensions")
        weights = clip_mask.to(embeddings.dtype).unsqueeze(-1)
        denominator = weights.sum(dim=1).clamp_min(1.0)
        return (embeddings * weights).sum(dim=1) / denominator

    def forward(
        self,
        clips: Tensor | None,
        metadata: Tensor | None,
        clip_mask: Tensor | None = None,
    ) -> Tensor:
        representations: list[Tensor] = []
        if self.input_mode in {"audio", "fusion"}:
            if clips is None:
                raise ValueError("clips are required for this input mode")
            representations.append(self._encode_audio(clips, clip_mask))
        if self.input_mode in {"clinical", "fusion"}:
            if metadata is None:
                raise ValueError("metadata is required for this input mode")
            if self.clinical_encoder is None:
                raise RuntimeError("clinical encoder is unavailable for this input mode")
            representations.append(self.clinical_encoder(metadata))
        return self.classifier(torch.cat(representations, dim=1))
