from __future__ import annotations

import torch
from torch import Tensor, nn


VALID_INPUT_MODES = frozenset({"audio", "clinical", "fusion"})
SPECTROGRAM_CLINICAL_BASELINE_V1 = "spectrogram_clinical_baseline_v1"
SPECTROGRAM_AUDIO_CNN_V1 = "spectrogram_audio_cnn_v1"
RESIDUAL_SPECTROGRAM_CNN_V2 = "residual_spectrogram_cnn_v2"
SUPPORTED_ARCHITECTURES = frozenset(
    {
        SPECTROGRAM_CLINICAL_BASELINE_V1,
        SPECTROGRAM_AUDIO_CNN_V1,
        RESIDUAL_SPECTROGRAM_CNN_V2,
    }
)


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


class ResidualBlock(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, *, stride: int) -> None:
        super().__init__()
        self.residual = nn.Sequential(
            nn.Conv2d(
                input_channels,
                output_channels,
                kernel_size=3,
                stride=stride,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(output_channels),
            nn.SiLU(),
            nn.Conv2d(
                output_channels,
                output_channels,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(output_channels),
        )
        self.shortcut = (
            nn.Identity()
            if input_channels == output_channels and stride == 1
            else nn.Sequential(
                nn.Conv2d(
                    input_channels,
                    output_channels,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(output_channels),
            )
        )
        self.activation = nn.SiLU()

    def forward(self, inputs: Tensor) -> Tensor:
        return self.activation(self.residual(inputs) + self.shortcut(inputs))


class ResidualSpectrogramClassifier(nn.Module):
    """Random-initialized residual CNN with patient-level clip aggregation."""

    def __init__(
        self,
        *,
        expected_n_mels: int = 64,
        expected_target_frames: int = 101,
        dropout: float = 0.25,
    ) -> None:
        super().__init__()
        self.input_mode = "audio"
        self.expected_n_mels = expected_n_mels
        self.expected_target_frames = expected_target_frames
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(16),
            nn.SiLU(),
            ResidualBlock(16, 16, stride=1),
            ResidualBlock(16, 32, stride=2),
            ResidualBlock(32, 64, stride=2),
            ResidualBlock(64, 128, stride=2),
            nn.BatchNorm2d(128),
            nn.SiLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Sequential(nn.Dropout(dropout), nn.Linear(128, 2))

    def forward_clips(self, clips: Tensor) -> Tensor:
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 4 or clips.shape[1:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(clips, 1, {self.expected_n_mels}, {self.expected_target_frames})"
            )
        return self.classifier(self.encoder(clips).flatten(1))

    def forward(
        self,
        clips: Tensor | None,
        metadata: Tensor | None,
        clip_mask: Tensor | None = None,
    ) -> Tensor:
        del metadata
        if clips is None:
            raise ValueError("clips are required for this input mode")
        if clips.ndim == 4:
            clips = clips.unsqueeze(1)
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 5 or clips.shape[2:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(batch, clips, 1, {self.expected_n_mels}, "
                f"{self.expected_target_frames})"
            )
        batch_size, clip_count = clips.shape[:2]
        probabilities = torch.softmax(
            self.forward_clips(clips.flatten(0, 1)),
            dim=1,
        ).view(batch_size, clip_count, 2)
        if clip_mask is None:
            patient_probabilities = probabilities.mean(dim=1)
        else:
            if clip_mask.shape != (batch_size, clip_count):
                raise ValueError("clip_mask must match the first two clip dimensions")
            weights = clip_mask.to(probabilities.dtype).unsqueeze(-1)
            denominator = weights.sum(dim=1).clamp_min(1.0)
            patient_probabilities = (probabilities * weights).sum(dim=1) / denominator
        return torch.log(patient_probabilities.clamp_min(1e-7))


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
        expected_n_mels: int = 128,
        expected_target_frames: int = 91,
    ) -> None:
        super().__init__()
        if input_mode not in VALID_INPUT_MODES:
            raise ValueError("input_mode must be audio, clinical, or fusion")
        if input_mode in {"clinical", "fusion"} and metadata_dim < 1:
            raise ValueError("metadata_dim must be positive for clinical input")

        self.input_mode = input_mode
        self.expected_n_mels = expected_n_mels
        self.expected_target_frames = expected_target_frames
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
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 5 or clips.shape[2:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(batch, clips, 1, {self.expected_n_mels}, "
                f"{self.expected_target_frames})"
            )
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


def build_screening_model(
    architecture: str,
    *,
    metadata_dim: int,
    input_mode: str,
    expected_n_mels: int,
    expected_target_frames: int,
) -> nn.Module:
    """Construct an explicitly versioned topology without loading any weights."""
    if architecture == RESIDUAL_SPECTROGRAM_CNN_V2:
        if input_mode != "audio" or metadata_dim != 0:
            raise ValueError("residual_spectrogram_cnn_v2 only supports audio input")
        return ResidualSpectrogramClassifier(
            expected_n_mels=expected_n_mels,
            expected_target_frames=expected_target_frames,
        )
    if architecture in {
        SPECTROGRAM_CLINICAL_BASELINE_V1,
        SPECTROGRAM_AUDIO_CNN_V1,
    }:
        return SpectrogramClinicalClassifier(
            metadata_dim=metadata_dim,
            input_mode=input_mode,
            expected_n_mels=expected_n_mels,
            expected_target_frames=expected_target_frames,
        )
    raise ValueError(f"unsupported model architecture: {architecture}")
