from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor
from torch.nn import Module

from src.audio_features import AudioFeatureConfig, extract_log_mel
from src.model import (
    RESIDUAL_SPECTROGRAM_CNN_V2,
    SPECTROGRAM_AUDIO_CNN_V1,
    ResidualSpectrogramClassifier,
    build_screening_model,
)
from training.dataset import PatientExample
from training.evaluator import EvaluationResult, evaluate_model
from training.metrics import (
    calculate_binary_metrics,
    select_threshold_for_minimum_sensitivity,
)
from training.pipeline import build_candidate_manifest
from training.runner import (
    Batch,
    train_one_epoch,
    train_patient_equal_clip_epoch,
)
from training.split import PatientPartitions, split_by_patient
from training.tb_screen_dataset import load_tb_screen_examples

DEFAULT_AUDIO_CONFIG = AudioFeatureConfig()
RESIDUAL_AUDIO_CONFIG = AudioFeatureConfig.tb_screen_reference()
METADATA_DIM = 0
DEFAULT_MAX_CLIPS_PER_SUBJECT = 20
DEFAULT_ELEVATED_SENSITIVITY = 1.0
DEFAULT_HIGHER_SENSITIVITY = 0.8


@dataclass(frozen=True)
class PreparedPatient:
    patient_id: str
    label: int
    clips: np.ndarray


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def _resolve_device(requested: str) -> torch.device:
    normalized = requested.strip().casefold()
    if normalized == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if normalized == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if normalized not in {"cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    return torch.device(normalized)


def _prepare_examples(
    examples: Sequence[PatientExample],
    audio_config: AudioFeatureConfig,
    *,
    partition_name: str,
) -> tuple[PreparedPatient, ...]:
    prepared: list[PreparedPatient] = []
    clip_count = sum(len(example.audio_paths) for example in examples)
    print(
        f"extracting {clip_count} {partition_name} clips with "
        f"{audio_config.duration_seconds:.2f}s windows",
        flush=True,
    )
    for index, example in enumerate(examples, start=1):
        clips = np.stack(
            [
                extract_log_mel(audio_path.read_bytes(), audio_config)
                for audio_path in example.audio_paths
            ]
        )
        prepared.append(PreparedPatient(example.patient_id, example.label, clips))
        if index % 20 == 0 or index == len(examples):
            print(
                f"prepared {partition_name} subjects: {index}/{len(examples)}",
                flush=True,
            )
    return tuple(prepared)


def _augment_clips(clips: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    augmented = clips.copy()
    for clip in augmented:
        spectrogram = clip[0]
        if rng.random() < 0.5:
            shift = int(rng.integers(-5, 6))
            spectrogram[:] = np.roll(spectrogram, shift, axis=1)
        if rng.random() < 0.5:
            width = int(rng.integers(1, min(9, spectrogram.shape[0]) + 1))
            start = int(rng.integers(0, spectrogram.shape[0] - width + 1))
            spectrogram[start : start + width, :] = 0.0
        if rng.random() < 0.5:
            width = int(rng.integers(1, min(7, spectrogram.shape[1]) + 1))
            start = int(rng.integers(0, spectrogram.shape[1] - width + 1))
            spectrogram[:, start : start + width] = 0.0
    return augmented


def _build_audio_batch(
    examples: Sequence[PreparedPatient],
    audio_config: AudioFeatureConfig,
    *,
    augmentation_rng: np.random.Generator | None = None,
) -> Batch:
    labels = torch.tensor([example.label for example in examples], dtype=torch.long)
    clip_arrays = [
        _augment_clips(example.clips, augmentation_rng)
        if augmentation_rng is not None
        else example.clips
        for example in examples
    ]
    max_clips = max(len(clips) for clips in clip_arrays)
    padded = np.zeros(
        (
            len(clip_arrays),
            max_clips,
            1,
            audio_config.n_mels,
            audio_config.target_frames,
        ),
        dtype=np.float32,
    )
    mask = np.zeros((len(clip_arrays), max_clips), dtype=bool)
    for index, clips in enumerate(clip_arrays):
        padded[index, : len(clips)] = clips
        mask[index, : len(clips)] = True
    return (
        torch.from_numpy(padded),
        torch.from_numpy(mask),
        torch.empty(0),
        labels,
    )


def _batches(
    examples: Sequence[PreparedPatient],
    batch_size: int,
    audio_config: AudioFeatureConfig,
    *,
    augmentation_rng: np.random.Generator | None = None,
) -> list[Batch]:
    return [
        _build_audio_batch(
            examples[start : start + batch_size],
            audio_config,
            augmentation_rng=augmentation_rng,
        )
        for start in range(0, len(examples), batch_size)
    ]


def _evaluate(
    model: Module,
    batches: Sequence[Batch],
    *,
    device: torch.device,
) -> EvaluationResult:
    return evaluate_model(model, batches, device=device)


def _class_weights(examples: Sequence[PreparedPatient]) -> Tensor:
    class_counts = torch.bincount(
        torch.tensor([example.label for example in examples]),
        minlength=2,
    ).float()
    if torch.any(class_counts == 0):
        raise ValueError("both TBscreen classes are required for training")
    return len(examples) / (2.0 * class_counts)


def _subject_hash(records: Sequence[PatientExample]) -> str:
    payload = "\n".join(sorted(record.patient_id for record in records)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _partition_summary(
    partitions: PatientPartitions[PatientExample],
) -> dict[str, dict[str, int | str]]:
    summary: dict[str, dict[str, int | str]] = {}
    for name, records in (
        ("train", partitions.train),
        ("validation", partitions.validation),
        ("test", partitions.test),
    ):
        summary[name] = {
            "subjects": len(records),
            "tb": sum(record.label == 1 for record in records),
            "non_tb": sum(record.label == 0 for record in records),
            "clips": sum(len(record.audio_paths) for record in records),
            "subject_id_sha256": _subject_hash(records),
        }
    return summary


def _exclusion_summary(subjects: Sequence[str]) -> dict[str, int]:
    return {"count": len(set(subjects))}


def _ordered_thresholds(elevated: float, higher: float) -> dict[str, float]:
    elevated_value = min(max(float(elevated), 0.0), 1.0)
    higher_value = min(max(float(higher), 0.0), 1.0)
    if elevated_value > higher_value:
        raise ValueError("elevated threshold must not exceed higher threshold")
    return {"elevated": elevated_value, "higher": higher_value}


def train_audio_model(
    partitions: PatientPartitions[PatientExample],
    *,
    epochs: int,
    batch_size: int,
    seed: int,
    output_dir: Path,
    device: torch.device,
    elevated_sensitivity: float,
    higher_sensitivity: float,
    use_augmentation: bool,
    architecture: str = RESIDUAL_SPECTROGRAM_CNN_V2,
    excluded_subjects: Sequence[str] = (),
) -> Path:
    """Train a random-initialized audio CNN and save the best validation epoch."""
    if elevated_sensitivity < higher_sensitivity:
        raise ValueError("elevated sensitivity target must be at least the higher target")
    _set_seed(seed)
    audio_config = (
        RESIDUAL_AUDIO_CONFIG
        if architecture == RESIDUAL_SPECTROGRAM_CNN_V2
        else DEFAULT_AUDIO_CONFIG
    )
    model = build_screening_model(
        architecture,
        metadata_dim=METADATA_DIM,
        input_mode="audio",
        expected_n_mels=audio_config.n_mels,
        expected_target_frames=audio_config.target_frames,
    ).to(device)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    print(
        f"training device={device} parameters={parameter_count} "
        f"augmentation={use_augmentation}",
        flush=True,
    )

    prepared_train = _prepare_examples(
        partitions.train,
        audio_config,
        partition_name="train",
    )
    prepared_validation = _prepare_examples(
        partitions.validation,
        audio_config,
        partition_name="validation",
    )
    prepared_test = _prepare_examples(
        partitions.test,
        audio_config,
        partition_name="test",
    )
    validation_batches = _batches(
        prepared_validation,
        batch_size,
        audio_config,
    )
    test_batches = _batches(prepared_test, batch_size, audio_config)

    learning_rate = 1e-3 if architecture == RESIDUAL_SPECTROGRAM_CNN_V2 else 3e-4
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=1e-4,
    )
    weights = _class_weights(prepared_train)
    best_state: dict[str, Tensor] | None = None
    best_validation_auroc = float("-inf")
    best_epoch = 0
    training_history: list[dict[str, object]] = []
    batch_random = random.Random(seed)

    for epoch in range(epochs):
        epoch_examples = list(prepared_train)
        batch_random.shuffle(epoch_examples)
        augmentation_rng = (
            np.random.default_rng(seed + epoch + 1) if use_augmentation else None
        )
        train_batches = _batches(
            epoch_examples,
            batch_size,
            audio_config,
            augmentation_rng=augmentation_rng,
        )
        if isinstance(model, ResidualSpectrogramClassifier):
            loss = train_patient_equal_clip_epoch(
                model,
                optimizer,
                train_batches,
                device=device,
                class_weights=weights,
            )
        else:
            loss = train_one_epoch(
                model,
                optimizer,
                train_batches,
                device=device,
                class_weights=weights,
            )
        validation = _evaluate(model, validation_batches, device=device)
        validation_auroc = validation.metrics["auroc"]
        score = float(validation_auroc) if validation_auroc is not None else float("-inf")
        if score > best_validation_auroc:
            best_validation_auroc = score
            best_epoch = epoch + 1
            best_state = {
                name: tensor.detach().cpu().clone()
                for name, tensor in model.state_dict().items()
            }
        training_history.append(
            {
                "epoch": epoch + 1,
                "training_loss": loss,
                "validation": validation.metrics,
            }
        )
        print(
            f"audio epoch={epoch + 1}/{epochs} loss={loss:.4f} "
            f"val={validation.metrics}",
            flush=True,
        )

    if best_state is None:
        raise RuntimeError("training produced no validation checkpoint")
    model.load_state_dict(best_state)
    model.to(device)
    validation = _evaluate(model, validation_batches, device=device)

    elevated_threshold = select_threshold_for_minimum_sensitivity(
        validation.labels,
        validation.probabilities,
        elevated_sensitivity,
    )
    higher_threshold = select_threshold_for_minimum_sensitivity(
        validation.labels,
        validation.probabilities,
        higher_sensitivity,
    )
    thresholds = _ordered_thresholds(elevated_threshold, higher_threshold)
    validation_operating_points = {
        name: calculate_binary_metrics(
            validation.labels,
            validation.probabilities,
            threshold,
        )
        for name, threshold in thresholds.items()
    }

    test_result = _evaluate(model, test_batches, device=device)
    test_operating_points = {
        name: calculate_binary_metrics(
            test_result.labels,
            test_result.probabilities,
            threshold,
        )
        for name, threshold in thresholds.items()
    }

    artifact_path = output_dir / "model-audio.pt"
    torch.save(best_state, artifact_path)
    evaluation = {
        "best_epoch": best_epoch,
        "validation": validation.metrics,
        "test": test_result.metrics,
        "operating_points": {
            "selection_split": "validation",
            "sensitivity_targets": {
                "elevated": elevated_sensitivity,
                "higher": higher_sensitivity,
            },
            "thresholds": thresholds,
            "validation": validation_operating_points,
            "test": test_operating_points,
        },
        "partitions": _partition_summary(partitions),
        "excluded_subjects": _exclusion_summary(excluded_subjects),
        "training": {
            "device": str(device),
            "augmentation": use_augmentation,
            "learning_rate": learning_rate,
            "parameter_count": parameter_count,
            "max_clips_per_subject": max(
                len(record.audio_paths)
                for records in (partitions.train, partitions.validation, partitions.test)
                for record in records
            ),
        },
        "training_history": training_history,
    }
    manifest_path = build_candidate_manifest(
        artifact_path,
        output_dir / "manifest-audio.json",
        model_name="SuaraNafas TBscreen residual audio CNN",
        model_version="3.0.0-research-candidate",
        input_mode="audio",
        metadata_dim=METADATA_DIM,
        supported_countries=["KE"],
        preprocessing={"audio": audio_config.to_manifest()},
        evaluation=evaluation,
        thresholds=thresholds,
        training_dataset="TBscreen passive cough",
        architecture=architecture,
        initialization="random_pytorch_default",
        pretrained_weights=False,
        seed=seed,
    )
    (output_dir / "metrics-audio.json").write_text(
        json.dumps(evaluation, indent=2),
        encoding="utf-8",
    )
    print(f"saved blocked candidate manifest: {manifest_path}", flush=True)
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a patient-level TBscreen audio CNN from random initialization"
    )
    parser.add_argument("--passive-metadata", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("training-output-v2"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--max-clips-per-subject",
        type=int,
        default=DEFAULT_MAX_CLIPS_PER_SUBJECT,
    )
    parser.add_argument(
        "--elevated-sensitivity",
        type=float,
        default=DEFAULT_ELEVATED_SENSITIVITY,
    )
    parser.add_argument(
        "--higher-sensitivity",
        type=float,
        default=DEFAULT_HIGHER_SENSITIVITY,
    )
    parser.add_argument("--exclude-subject", action="append", default=[])
    parser.add_argument("--no-augmentation", action="store_true")
    parser.add_argument(
        "--architecture",
        choices=(RESIDUAL_SPECTROGRAM_CNN_V2, SPECTROGRAM_AUDIO_CNN_V1),
        default=RESIDUAL_SPECTROGRAM_CNN_V2,
    )
    args = parser.parse_args()

    if args.epochs < 1 or args.batch_size < 1 or args.max_clips_per_subject < 1:
        raise ValueError("epochs, batch-size, and max-clips-per-subject must be positive")
    device = _resolve_device(args.device)
    examples = load_tb_screen_examples(
        (args.passive_metadata,),
        args.audio_root,
        max_clips=args.max_clips_per_subject,
    )
    available_subjects = {example.patient_id for example in examples}
    excluded_subjects = set(args.exclude_subject)
    missing_exclusions = excluded_subjects - available_subjects
    if missing_exclusions:
        raise ValueError("excluded subject was not found in the dataset")
    examples = [
        example for example in examples if example.patient_id not in excluded_subjects
    ]
    partitions = split_by_patient(
        examples,
        seed=args.seed,
        validation_fraction=0.2,
        test_fraction=0.2,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        json.dumps(
            {
                "device": str(device),
                "partitions": _partition_summary(partitions),
                "excluded_subjects": _exclusion_summary(tuple(excluded_subjects)),
            },
            indent=2,
        ),
        flush=True,
    )
    train_audio_model(
        partitions,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
        output_dir=args.output_dir,
        device=device,
        elevated_sensitivity=args.elevated_sensitivity,
        higher_sensitivity=args.higher_sensitivity,
        use_augmentation=not args.no_augmentation,
        architecture=args.architecture,
        excluded_subjects=tuple(excluded_subjects),
    )


if __name__ == "__main__":
    main()
