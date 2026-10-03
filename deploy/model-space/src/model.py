from __future__ import annotations

import torch
from torch import Tensor, nn


VALID_INPUT_MODES = frozenset({"audio", "clinical", "fusion"})
SPECTROGRAM_CLINICAL_BASELINE_V1 = "spectrogram_clinical_baseline_v1"
SPECTROGRAM_AUDIO_CNN_V1 = "spectrogram_audio_cnn_v1"
RESIDUAL_SPECTROGRAM_CNN_V2 = "residual_spectrogram_cnn_v2"
RESIDUAL_FUSION_CNN_V3 = "residual_fusion_cnn_v3"
RESIDUAL_TABULAR_FUSION_V4 = "residual_tabular_fusion_v4"
SUPPORTED_ARCHITECTURES = frozenset(
    {
        SPECTROGRAM_CLINICAL_BASELINE_V1,
        SPECTROGRAM_AUDIO_CNN_V1,
        RESIDUAL_SPECTROGRAM_CNN_V2,
        RESIDUAL_FUSION_CNN_V3,
        RESIDUAL_TABULAR_FUSION_V4,
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


class ResidualFusionClassifier(nn.Module):
    """Residual audio CNN fused with clinical variables at the patient level.

    ``residual_spectrogram_cnn_v2`` throws the clinical tensor away
    (``del metadata``) even though the screening form collects every CODA TB
    variable. Published work on this exact task reports large gains from adding
    those variables, so v3 keeps v2's clip aggregation intact and appends a
    patient-level clinical branch instead of discarding the input.

    The audio branch is a verbatim copy of v2's topology so that v3 can be
    warm-started from a v2 checkpoint and so the two remain directly
    comparable in a patient-level ablation.
    """

    def __init__(
        self,
        *,
        metadata_dim: int,
        expected_n_mels: int = 64,
        expected_target_frames: int = 101,
        dropout: float = 0.25,
        clinical_embedding_dim: int = 32,
    ) -> None:
        super().__init__()
        if metadata_dim < 1:
            raise ValueError("metadata_dim must be positive for a fusion model")
        self.input_mode = "fusion"
        self.metadata_dim = metadata_dim
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
        self.clip_classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(128, 2),
        )
        self.clinical_encoder = nn.Sequential(
            nn.Linear(metadata_dim, 64),
            nn.ReLU(),
            nn.Linear(64, clinical_embedding_dim),
            nn.ReLU(),
        )
        self.fusion_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(2 + clinical_embedding_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 2),
        )

    def _validated_clips(self, clips: Tensor) -> Tensor:
        if clips.ndim == 4:
            clips = clips.unsqueeze(1)
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 5 or clips.shape[2:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(batch, clips, 1, {self.expected_n_mels}, "
                f"{self.expected_target_frames})"
            )
        return clips

    def forward_clips(self, clips: Tensor) -> Tensor:
        """Per-clip audio logits, matching the v2 contract."""
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 4 or clips.shape[1:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(clips, 1, {self.expected_n_mels}, {self.expected_target_frames})"
            )
        return self.clip_classifier(self.encoder(clips).flatten(1))

    def _patient_audio_log_probabilities(
        self,
        clips: Tensor,
        clip_mask: Tensor | None,
    ) -> Tensor:
        clips = self._validated_clips(clips)
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

    def forward(
        self,
        clips: Tensor | None,
        metadata: Tensor | None,
        clip_mask: Tensor | None = None,
    ) -> Tensor:
        if clips is None:
            raise ValueError("clips are required for this input mode")
        audio_log_probabilities = self._patient_audio_log_probabilities(clips, clip_mask)
        if metadata is None:
            raise ValueError("metadata is required for this input mode")
        if metadata.ndim != 2 or metadata.shape[1] != self.metadata_dim:
            raise ValueError(
                f"metadata must have shape (batch, {self.metadata_dim})"
            )
        clinical_embedding = self.clinical_encoder(metadata)
        return self.fusion_head(
            torch.cat([audio_log_probabilities, clinical_embedding], dim=1)
        )


class TabularEncoder(nn.Module):
    """Wider, properly normalised clinical branch.

    v3 spent 3,872 parameters on the clinical side (27 -> 64 -> 32). That is
    not enough to represent what the literature reports these variables are
    worth: on CODA-TB, DeepGB-TB measures a gradient-boosted model on the
    demographics alone at 0.834 AUROC, higher than its own audio-only branch
    at 0.825. A 3,872-parameter MLP cannot carry that much signal.

    LayerNorm rather than BatchNorm: cohorts here are small enough that a
    batch of size 1 occurs, and BatchNorm1d raises on that during training.
    """

    def __init__(
        self,
        metadata_dim: int,
        embedding_dim: int = 64,
        *,
        hidden_dim: int = 128,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        if metadata_dim < 1:
            raise ValueError("metadata_dim must be positive")
        self.network = nn.Sequential(
            nn.Linear(metadata_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, embedding_dim),
            nn.SiLU(),
        )

    def forward(self, metadata: Tensor) -> Tensor:
        return self.network(metadata)


class GatedFusion(nn.Module):
    """Audio-conditioned modulation of the clinical embedding (FiLM-style).

    v3 concatenated patient-level audio log-probabilities with a clinical
    embedding and handed the pair to a linear layer. That can add the two
    signals but cannot express "these clinical values only matter if the audio
    agrees". The gate lets the audio branch scale and shift the clinical
    features, which is the interaction DeepGB-TB's cross-attention module is
    there to capture, at a fraction of the parameters and the overfitting
    risk at small N.
    """

    def __init__(
        self,
        audio_dim: int,
        clinical_dim: int,
        output_dim: int,
        *,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.gate = nn.Linear(audio_dim, clinical_dim * 2)
        self.joint = nn.Sequential(
            nn.Linear(audio_dim + clinical_dim, output_dim),
            nn.LayerNorm(output_dim),
            nn.SiLU(),
            nn.Dropout(dropout),
        )

    def forward(self, audio_embedding: Tensor, clinical_embedding: Tensor) -> Tensor:
        scale, shift = self.gate(audio_embedding).chunk(2, dim=1)
        modulated = clinical_embedding * (1.0 + torch.tanh(scale)) + shift
        return self.joint(torch.cat([audio_embedding, modulated], dim=1))


class ResidualTabularFusionClassifier(nn.Module):
    """Audio CNN plus a capacity-appropriate clinical branch, fused by gating.

    Motivation is measured, not stylistic:

    * The clinical branch is enlarged because the demographic variables
      dominate this task in the published ablations (0.834 tabular-only vs
      0.825 audio-only on CODA-TB), and v3's branch was far too small.
    * Fusion is gated rather than concatenated because the largest single
      contributor in the published ablation is the multimodal step itself
      (+6.7% AUROC), not the attention mechanism on top of it (+1.2%).
    * The patient-level audio log-probability path from v2/v3 is retained, so
      v4 stays directly comparable to them in a patient-level ablation.

    Still randomly initialised: no pretrained weights, no from-scratch claim
    is weakened.
    """

    def __init__(
        self,
        *,
        metadata_dim: int,
        expected_n_mels: int = 64,
        expected_target_frames: int = 101,
        dropout: float = 0.25,
        clinical_embedding_dim: int = 64,
        audio_embedding_dim: int = 64,
        fused_dim: int = 64,
    ) -> None:
        super().__init__()
        if metadata_dim < 1:
            raise ValueError("metadata_dim must be positive for a fusion model")
        self.input_mode = "fusion"
        self.metadata_dim = metadata_dim
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
        self.audio_projection = nn.Linear(128, audio_embedding_dim)
        self.clip_classifier = nn.Sequential(
            nn.Dropout(dropout), nn.Linear(audio_embedding_dim, 2)
        )
        self.tabular_encoder = TabularEncoder(
            metadata_dim, clinical_embedding_dim, dropout=dropout
        )
        self.fusion = GatedFusion(
            audio_embedding_dim, clinical_embedding_dim, fused_dim, dropout=dropout
        )
        self.classifier = nn.Sequential(
            nn.Dropout(dropout), nn.Linear(fused_dim + 2, 2)
        )

    def _validated_clips(self, clips: Tensor) -> Tensor:
        if clips.ndim != 5:
            raise ValueError("clips must have shape (batch, clips, channels, n_mels, frames)")
        if clips.shape[2] != 1:
            raise ValueError("clips must carry a single audio channel")
        if clips.shape[3] != self.expected_n_mels or clips.shape[4] != self.expected_target_frames:
            raise ValueError(
                f"clips must have shape (batch, clips, 1, {self.expected_n_mels}, "
                f"{self.expected_target_frames})"
            )
        return clips

    def forward_clips(self, clips: Tensor) -> Tensor:
        """Per-clip audio logits, matching the v2/v3 contract the trainer uses.

        The runner calls this with a 4D ``(clips, 1, n_mels, frames)`` batch,
        so it must not go through the 5D patient-level shape check.
        """
        expected_shape = (1, self.expected_n_mels, self.expected_target_frames)
        if clips.ndim != 4 or clips.shape[1:] != expected_shape:
            raise ValueError(
                "clips must have shape "
                f"(clips, 1, {self.expected_n_mels}, {self.expected_target_frames})"
            )
        return self.clip_classifier(
            self.audio_projection(self.encoder(clips).flatten(1))
        )

    def _patient_audio(
        self, clips: Tensor, clip_mask: Tensor | None
    ) -> tuple[Tensor, Tensor]:
        """Patient-level audio embedding and log-probabilities.

        The convolutional trunk runs once and both outputs are derived from
        the same per-clip embedding, so the fused head never sees a different
        audio representation than the clip-level logits.
        """
        clips = self._validated_clips(clips)
        batch_size, clip_count = clips.shape[:2]
        embeddings = self.audio_projection(
            self.encoder(clips.flatten(0, 1)).flatten(1)
        ).view(batch_size, clip_count, -1)
        probabilities = torch.softmax(
            self.clip_classifier(embeddings.flatten(0, 1)), dim=1
        ).view(batch_size, clip_count, 2)
        if clip_mask is None:
            mask = None
        else:
            if clip_mask.shape != (batch_size, clip_count):
                raise ValueError("clip_mask must match the first two clip dimensions")
            mask = clip_mask.unsqueeze(-1)
        if mask is None:
            return embeddings.mean(dim=1), torch.log(
                probabilities.mean(dim=1).clamp_min(1e-7)
            )
        denominator = mask.sum(dim=1).clamp_min(1.0)
        patient_embedding = (embeddings * mask).sum(dim=1) / denominator
        patient_probabilities = (probabilities * mask).sum(dim=1) / denominator
        return patient_embedding, torch.log(patient_probabilities.clamp_min(1e-7))

    def forward(
        self,
        clips: Tensor | None,
        metadata: Tensor | None,
        clip_mask: Tensor | None = None,
    ) -> Tensor:
        if clips is None:
            raise ValueError("clips are required for this input mode")
        if metadata is None:
            raise ValueError("metadata is required for this input mode")
        if metadata.ndim != 2 or metadata.shape[1] != self.metadata_dim:
            raise ValueError(f"metadata must have shape (batch, {self.metadata_dim})")
        audio_embedding, audio_log_probabilities = self._patient_audio(clips, clip_mask)
        clinical_embedding = self.tabular_encoder(metadata)
        fused = self.fusion(audio_embedding, clinical_embedding)
        return self.classifier(torch.cat([fused, audio_log_probabilities], dim=1))


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
    if architecture == RESIDUAL_FUSION_CNN_V3:
        if input_mode != "fusion" or metadata_dim < 1:
            raise ValueError("residual_fusion_cnn_v3 requires fusion input and metadata_dim")
        return ResidualFusionClassifier(
            metadata_dim=metadata_dim,
            expected_n_mels=expected_n_mels,
            expected_target_frames=expected_target_frames,
        )
    if architecture == RESIDUAL_TABULAR_FUSION_V4:
        if input_mode != "fusion" or metadata_dim < 1:
            raise ValueError(
                "residual_tabular_fusion_v4 requires fusion input and a positive metadata_dim"
            )
        return ResidualTabularFusionClassifier(
            metadata_dim=metadata_dim,
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
