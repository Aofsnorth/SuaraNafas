from __future__ import annotations

import argparse
import copy
import json
import random
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from src.audio_features import AudioFeatureConfig, extract_log_mel
from src.model import SpectrogramClinicalClassifier
from training.dataset import PatientExample
from training.evaluator import EvaluationResult, evaluate_model
from training.pipeline import build_candidate_manifest
from training.runner import Batch, train_one_epoch
from training.split import PatientPartitions, split_by_patient
from training.tb_screen_dataset import load_tb_screen_examples

DEFAULT_AUDIO_CONFIG = AudioFeatureConfig()
METADATA_DIM = 0
MAX_CLIPS_PER_SUBJECT = 8


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _build_audio_batch(
    examples: Sequence[PatientExample],
    audio_config: AudioFeatureConfig,
) -> Batch:
    labels = torch.tensor([example.label for example in examples], dtype=torch.long)
    clip_arrays = [
        np.stack(
            [
                extract_log_mel(audio_path.read_bytes(), audio_config)
                for audio_path in example.audio_paths
            ]
        )
        for example in examples
    ]
    max_clips = max(len(clips) for clips in clip_arrays)
    padded = np.zeros(
        (len(clip_arrays), max_clips, 1, audio_config.n_mels, audio_config.target_frames),
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
    examples: Sequence[PatientExample],
    batch_size: int,
    audio_config: AudioFeatureConfig,
) -> list[Batch]:
    return [
        _build_audio_batch(examples[start : start + batch_size], audio_config)
        for start in range(0, len(examples), batch_size)
    ]


def _evaluate(
    model: SpectrogramClinicalClassifier,
    batches: Sequence[Batch],
) -> EvaluationResult:
    return evaluate_model(model, batches)


def _class_weights(examples: Sequence[PatientExample]) -> Tensor:
    class_counts = torch.bincount(
        torch.tensor([example.label for example in examples]),
        minlength=2,
    ).float()
    if torch.any(class_counts == 0):
        raise ValueError("both TBscreen classes are required for training")
    return len(examples) / (2.0 * class_counts)


def _partition_summary(
    partitions: PatientPartitions[PatientExample],
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
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
        }
    return summary


def train_audio_model(
    partitions: PatientPartitions[PatientExample],
    *,
    epochs: int,
    batch_size: int,
    seed: int,
    output_dir: Path,
) -> Path:
    """Train a random-initialized audio CNN and save the best validation epoch."""
    _set_seed(seed)
    model = SpectrogramClinicalClassifier(
        metadata_dim=METADATA_DIM,
        input_mode="audio",
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    train_batches = _batches(partitions.train, batch_size, DEFAULT_AUDIO_CONFIG)
    validation_batches = _batches(
        partitions.validation,
        batch_size,
        DEFAULT_AUDIO_CONFIG,
    )
    test_batches = _batches(partitions.test, batch_size, DEFAULT_AUDIO_CONFIG)
    weights = _class_weights(partitions.train)
    best_state: dict[str, Tensor] | None = None
    best_validation_auroc = float("-inf")
    best_epoch = 0
    training_history: list[dict[str, object]] = []
    batch_random = random.Random(seed)

    for epoch in range(epochs):
        batch_random.shuffle(train_batches)
        loss = train_one_epoch(
            model,
            optimizer,
            train_batches,
            class_weights=weights,
        )
        validation = _evaluate(model, validation_batches)
        validation_auroc = validation.metrics["auroc"]
        score = float(validation_auroc) if validation_auroc is not None else float("-inf")
        if score > best_validation_auroc:
            best_validation_auroc = score
            best_epoch = epoch + 1
            best_state = copy.deepcopy(model.state_dict())
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
    validation = _evaluate(model, validation_batches)
    test_result = _evaluate(model, test_batches)

    artifact_path = output_dir / "model-audio.pt"
    torch.save(model.state_dict(), artifact_path)
    evaluation = {
        "best_epoch": best_epoch,
        "validation": validation.metrics,
        "test": test_result.metrics,
        "partitions": _partition_summary(partitions),
        "training_history": training_history,
    }
    manifest_path = build_candidate_manifest(
        artifact_path,
        output_dir / "manifest-audio.json",
        model_name="SuaraNafas TBscreen audio CNN",
        model_version="1.0.0-candidate",
        input_mode="audio",
        metadata_dim=METADATA_DIM,
        supported_countries=["KE"],
        preprocessing={"audio": DEFAULT_AUDIO_CONFIG.__dict__},
        evaluation=evaluation,
        training_dataset="TBscreen",
        architecture="spectrogram_audio_cnn_v1",
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
    parser.add_argument("--output-dir", type=Path, default=Path("training-output"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError("epochs and batch-size must be positive")
    examples = load_tb_screen_examples(
        (args.passive_metadata,),
        args.audio_root,
        max_clips=MAX_CLIPS_PER_SUBJECT,
    )
    partitions = split_by_patient(
        examples,
        seed=args.seed,
        validation_fraction=0.2,
        test_fraction=0.2,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(json.dumps(_partition_summary(partitions), indent=2), flush=True)
    train_audio_model(
        partitions,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
