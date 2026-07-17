from __future__ import annotations

import io
import json
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping, Sequence

import librosa
import numpy as np
import soundfile as sf
import torch


DEFAULT_CONFIG_PATH = Path(__file__).with_name("deployment_config.json")


@dataclass(frozen=True)
class PreparedInputs:
    patient_specs: torch.Tensor
    metadata: torch.Tensor
    accepted_clips: int


class PreprocessingError(ValueError):
    pass


def load_deployment_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing {config_path}. Run export_deployment_config.py before deployment."
        )
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalise_choice(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _binary(value: Any, *, allow_unknown: bool = False) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) in (0.0, 1.0):
            return float(value)

    normalised = _normalise_choice(value)
    if normalised in {"yes", "true", "1", "male", "positive"}:
        return 1.0
    if normalised in {"no", "false", "0", "female", "negative"}:
        return 0.0
    if allow_unknown and normalised in {"", "unknown", "not sure", "unsure", "none"}:
        return 0.0
    raise PreprocessingError(f"Unsupported binary value: {value!r}")


def _numeric(
    payload: Mapping[str, Any],
    field: str,
    stats: Mapping[str, Mapping[str, float]],
) -> float:
    stat = stats[field]
    raw_value = payload.get(field)
    if raw_value in (None, ""):
        value = float(stat["mean"])
    else:
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise PreprocessingError(f"{field} must be numeric") from exc

    return (value - float(stat["mean"])) / (float(stat["std"]) + 1e-8)


def encode_clinical_metadata(
    payload: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    cough_count: int,
) -> np.ndarray:
    """Encode the 27 clinical features in the exact training column order."""
    feature_order = config["clinical_feature_order"]
    stats = config["numeric_stats"]
    encoded: dict[str, float] = {feature: 0.0 for feature in feature_order}

    encoded["sex"] = _binary(payload.get("sex"), allow_unknown=True)

    for field in config["numeric_features"]:
        encoded[field] = _numeric(payload, field, stats)

    for field in config["binary_features"]:
        encoded[field] = _binary(payload.get(field), allow_unknown=True)

    encoded["Numberofcoughsoundscollected"] = float(cough_count)

    country = str(payload.get("Country", payload.get("country", ""))).strip().upper()
    country_feature = f"country_{country}"
    if country_feature not in encoded:
        allowed = ", ".join(config["countries"])
        raise PreprocessingError(f"Unsupported country {country!r}. Allowed: {allowed}")
    encoded[country_feature] = 1.0

    hiv_value = _normalise_choice(payload.get("HIVstatus", payload.get("hiv_status")))
    hiv_lookup = {
        "negative": "hiv_Negative",
        "positive": "hiv_Positive",
        "unknown": "hiv_Unknown",
        "not sure": "hiv_Unknown",
        "": "hiv_Unknown",
    }
    hiv_feature = hiv_lookup.get(hiv_value)
    if hiv_feature is None:
        raise PreprocessingError(
            "HIVstatus must be Negative, Positive, or Unknown"
        )
    encoded[hiv_feature] = 1.0

    return np.asarray([encoded[column] for column in feature_order], dtype=np.float32)


def _load_audio_source(
    source: str | Path | bytes | bytearray | BinaryIO | tuple[np.ndarray, int],
) -> tuple[np.ndarray, int]:
    if isinstance(source, tuple):
        samples, sample_rate = source
        return np.asarray(samples, dtype=np.float32), int(sample_rate)

    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
        try:
            samples, sample_rate = sf.read(
                io.BytesIO(data), dtype="float32", always_2d=False
            )
            return np.asarray(samples), int(sample_rate)
        except Exception:
            # Browser MediaRecorder commonly produces WebM/Opus. Librosa's
            # FFmpeg/audioread fallback can decode it from a temporary file.
            with tempfile.NamedTemporaryFile(suffix=".audio") as temporary:
                temporary.write(data)
                temporary.flush()
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="PySoundFile failed.*")
                    warnings.filterwarnings("ignore", category=FutureWarning)
                    samples, sample_rate = librosa.load(
                        temporary.name, sr=None, mono=False
                    )
                return np.asarray(samples), int(sample_rate)

    if isinstance(source, io.IOBase):
        data = source.read()
        source.seek(0)
        return _load_audio_source(data)

    samples, sample_rate = sf.read(str(source), dtype="float32", always_2d=False)
    return np.asarray(samples), int(sample_rate)


def _prepare_waveform(
    source: str | Path | bytes | bytearray | BinaryIO | tuple[np.ndarray, int],
    config: Mapping[str, Any],
) -> np.ndarray:
    audio_config = config["audio"]
    target_sample_rate = int(audio_config["sample_rate"])
    target_length = round(float(audio_config["duration_seconds"]) * target_sample_rate)

    try:
        samples, sample_rate = _load_audio_source(source)
    except Exception as exc:
        raise PreprocessingError(f"Could not decode audio: {exc}") from exc

    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if samples.ndim != 1 or samples.size == 0:
        raise PreprocessingError("Audio must contain a non-empty mono or stereo waveform")
    if not np.all(np.isfinite(samples)):
        raise PreprocessingError("Audio contains NaN or infinite samples")

    samples = samples.astype(np.float32, copy=False)
    if sample_rate != target_sample_rate:
        samples = librosa.resample(
            samples,
            orig_sr=sample_rate,
            target_sr=target_sample_rate,
        )

    # Training cropped each already-segmented cough from its beginning.
    samples = samples[:target_length]
    if samples.size < target_length:
        samples = np.pad(samples, (0, target_length - samples.size))

    rms = float(np.sqrt(np.mean(np.square(samples))))
    if rms < float(audio_config.get("minimum_rms", 1e-5)):
        raise PreprocessingError("Audio is silent or too quiet")

    return samples


def extract_audio_features(
    source: str | Path | bytes | bytearray | BinaryIO | tuple[np.ndarray, int],
    config: Mapping[str, Any],
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return one Mel tensor (1, 128, 36) and one 16-D acoustic vector."""
    audio_config = config["audio"]
    sample_rate = int(audio_config["sample_rate"])
    samples = _prepare_waveform(source, config)

    mel = librosa.feature.melspectrogram(
        y=samples,
        sr=sample_rate,
        n_fft=int(audio_config["n_fft"]),
        hop_length=int(audio_config["hop_length"]),
        n_mels=int(audio_config["n_mels"]),
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_normalised = (mel_db - mel_db.min()) / (
        mel_db.max() - mel_db.min() + 1e-8
    )

    target_frames = int(audio_config["target_frames"])
    if mel_normalised.shape[1] < target_frames:
        mel_normalised = np.pad(
            mel_normalised,
            ((0, 0), (0, target_frames - mel_normalised.shape[1])),
        )
    else:
        mel_normalised = mel_normalised[:, :target_frames]

    mfcc_mean = librosa.feature.mfcc(
        y=samples,
        sr=sample_rate,
        n_mfcc=13,
    ).mean(axis=1)
    centroid_mean = librosa.feature.spectral_centroid(
        y=samples, sr=sample_rate
    ).mean()
    rolloff_mean = librosa.feature.spectral_rolloff(
        y=samples, sr=sample_rate
    ).mean()
    zcr_mean = librosa.feature.zero_crossing_rate(samples).mean()

    acoustic = np.concatenate(
        [mfcc_mean, [centroid_mean, rolloff_mean, zcr_mean]]
    ).astype(np.float32)
    acoustic[13] /= sample_rate / 2.0
    acoustic[14] /= sample_rate / 2.0

    spectrogram_tensor = torch.from_numpy(mel_normalised.astype(np.float32)).unsqueeze(0)
    acoustic_tensor = torch.from_numpy(acoustic)
    return spectrogram_tensor, acoustic_tensor


def prepare_model_inputs(
    audio_sources: Sequence[
        str | Path | bytes | bytearray | BinaryIO | tuple[np.ndarray, int]
    ],
    clinical_payload: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> PreparedInputs:
    config = dict(config or load_deployment_config())
    maximum_clips = int(config["audio"]["maximum_clips"])
    selected_sources = list(audio_sources)[:maximum_clips]
    if not selected_sources:
        raise PreprocessingError("At least one cough clip is required")

    spectrograms = []
    acoustic_vectors = []
    errors = []
    for index, source in enumerate(selected_sources, start=1):
        try:
            spectrogram, acoustic = extract_audio_features(source, config)
        except PreprocessingError as exc:
            errors.append(f"clip {index}: {exc}")
            continue
        spectrograms.append(spectrogram)
        acoustic_vectors.append(acoustic)

    if not spectrograms:
        detail = "; ".join(errors) or "no decodable clips"
        raise PreprocessingError(f"No valid cough clips: {detail}")

    clinical = encode_clinical_metadata(
        clinical_payload,
        config,
        cough_count=len(spectrograms),
    )
    averaged_acoustic = torch.stack(acoustic_vectors).mean(dim=0).numpy()
    metadata = np.concatenate([clinical, averaged_acoustic]).astype(np.float32)

    expected_metadata_dim = int(config["model"]["metadata_dim"])
    if metadata.size != expected_metadata_dim:
        raise RuntimeError(
            f"Metadata dimension mismatch: {metadata.size}, expected {expected_metadata_dim}"
        )

    return PreparedInputs(
        patient_specs=torch.stack(spectrograms),
        metadata=torch.from_numpy(metadata).unsqueeze(0),
        accepted_clips=len(spectrograms),
    )


def classify_risk(probability: float, config: Mapping[str, Any]) -> str:
    thresholds = config["thresholds"]
    if probability >= float(thresholds["default"]):
        return "higher"
    if probability >= float(thresholds["screening"]):
        return "elevated"
    return "lower"
