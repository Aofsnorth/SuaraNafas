from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.audio_features import AudioFeatureConfig, extract_log_mel
from src.audio_validation import AudioQuality
from src.metadata import ClinicalMetadata, encode_clinical_metadata
from src.model import SpectrogramClinicalClassifier
from src.model_gateway import (
    ModelInferenceError,
    ScreeningModel,
    ScreeningPrediction,
)
from training.artifact_manifest import (
    ArtifactManifest,
    ArtifactManifestError,
    load_artifact_manifest,
    verify_artifact_digest,
)


class ModelConfigurationError(RuntimeError):
    """Raised when a model artifact is not safe or compatible to load."""


def _resolve_artifact_path(manifest_path: Path, artifact_path: str) -> Path:
    candidate = (manifest_path.parent / artifact_path).resolve()
    try:
        candidate.relative_to(manifest_path.parent.resolve())
    except ValueError as error:
        raise ModelConfigurationError("model artifact must stay within its manifest directory") from error
    return candidate


def _required_runtime_config(
    manifest_path: Path,
    *,
    allow_blocked_candidate: bool,
) -> ArtifactManifest:
    try:
        manifest = load_artifact_manifest(
            manifest_path,
            allow_blocked_candidate=allow_blocked_candidate,
        )
    except ArtifactManifestError as error:
        raise ModelConfigurationError(str(error)) from error
    supported_architectures = {
        "spectrogram_clinical_baseline_v1",
        "spectrogram_audio_cnn_v1",
    }
    if manifest.architecture not in supported_architectures:
        raise ModelConfigurationError("unsupported model architecture")
    if manifest.input_mode not in {"audio", "fusion"}:
        raise ModelConfigurationError("runtime requires an audio-capable model")
    if manifest.input_mode == "fusion" and manifest.metadata_dim < 1:
        raise ModelConfigurationError("fusion model metadata_dim is required")
    if not manifest.supported_countries:
        raise ModelConfigurationError("manifest supported_countries is required")
    if not manifest.preprocessing:
        raise ModelConfigurationError("manifest preprocessing configuration is required")
    return manifest


class TorchScreeningModel:
    def __init__(
        self,
        model: SpectrogramClinicalClassifier,
        manifest: ArtifactManifest,
        feature_config: AudioFeatureConfig,
        device: torch.device,
    ) -> None:
        self._model = model
        self._manifest = manifest
        self._feature_config = feature_config
        self._device = device

    @property
    def is_available(self) -> bool:
        return True

    @property
    def supported_countries(self) -> frozenset[str]:
        return self._manifest.supported_countries

    @property
    def deployment_status(self) -> str:
        if self._manifest.external_validation:
            return "validated"
        return "candidate"

    def _risk_band(self, probability: float) -> str:
        if probability >= self._manifest.thresholds["higher"]:
            return "higher"
        if probability >= self._manifest.thresholds["elevated"]:
            return "elevated"
        return "lower"

    @staticmethod
    def _uncertainty(probability: float) -> float:
        probabilities = np.asarray([probability, 1.0 - probability], dtype=np.float64)
        entropy = -float(np.sum(probabilities * np.log(np.maximum(probabilities, 1e-12))))
        return entropy / float(np.log(2.0))

    def predict(
        self,
        audio: Sequence[bytes],
        qualities: Sequence[AudioQuality],
        metadata: ClinicalMetadata,
    ) -> ScreeningPrediction:
        if len(audio) == 0 or len(audio) != len(qualities):
            raise ModelInferenceError("audio and quality inputs are inconsistent")
        try:
            spectrograms = np.stack(
                [extract_log_mel(data, self._feature_config) for data in audio],
                axis=0,
            )
            clips = torch.from_numpy(spectrograms).unsqueeze(0).to(self._device)
            clinical: torch.Tensor | None = None
            if self._manifest.input_mode == "fusion":
                metadata_vector = np.asarray(
                    encode_clinical_metadata(
                        metadata,
                        self._manifest.preprocessing,
                        cough_count=len(audio),
                    ),
                    dtype=np.float32,
                )
                clinical = torch.from_numpy(metadata_vector).unsqueeze(0).to(self._device)
            with torch.inference_mode():
                logits = self._model(clips, clinical)
                probability = float(torch.softmax(logits, dim=1)[0, 1].item())
        except (ValueError, KeyError, TypeError, RuntimeError) as error:
            raise ModelInferenceError("model preprocessing or inference failed") from error

        return ScreeningPrediction(
            tb_risk_probability=probability,
            risk_band=self._risk_band(probability),
            accepted_clips=len(audio),
            quality_status="acceptable",
            uncertainty=self._uncertainty(probability),
            model_name=self._manifest.model_name,
            model_version=self._manifest.model_version,
            calibration_status=self._manifest.calibration_status,
        )


def _feature_config(manifest: ArtifactManifest) -> AudioFeatureConfig:
    audio = manifest.preprocessing.get("audio", {})
    return AudioFeatureConfig(
        sample_rate=int(audio.get("sample_rate", 16_000)),
        duration_seconds=float(audio.get("duration_seconds", 0.55)),
        n_mels=int(audio.get("n_mels", 128)),
        n_fft=int(audio.get("n_fft", 1_024)),
        hop_length=int(audio.get("hop_length", 256)),
        target_frames=int(audio.get("target_frames", 36)),
    )


def load_torch_screening_model(
    manifest_path: str | Path,
    *,
    device: str | torch.device = "cpu",
    allow_blocked_candidate: bool = False,
) -> TorchScreeningModel:
    """Load a checksum-verified validated model or an explicit local candidate."""
    path = Path(manifest_path).resolve()
    manifest = _required_runtime_config(
        path,
        allow_blocked_candidate=allow_blocked_candidate,
    )
    artifact_path = _resolve_artifact_path(path, manifest.artifact_path)
    try:
        verify_artifact_digest(artifact_path, manifest.artifact_sha256)
        state_dict = torch.load(artifact_path, map_location="cpu", weights_only=True)
        if not isinstance(state_dict, dict):
            raise ModelConfigurationError("model artifact must contain a state dictionary")
        model = SpectrogramClinicalClassifier(
            metadata_dim=manifest.metadata_dim,
            input_mode=manifest.input_mode,
        )
        model.load_state_dict(state_dict, strict=True)
    except ArtifactManifestError as error:
        raise ModelConfigurationError(str(error)) from error
    except (OSError, RuntimeError, TypeError) as error:
        raise ModelConfigurationError("model artifact could not be loaded") from error

    target_device = torch.device(device)
    return TorchScreeningModel(
        model.to(target_device).eval(),
        manifest,
        _feature_config(manifest),
        target_device,
    )
