from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from src.audio_features import AudioFeatureConfig
from src.model import RESIDUAL_SPECTROGRAM_CNN_V2, ResidualSpectrogramClassifier
from training.dataset import PatientExample
from training.evaluator import EvaluationResult
from training.metrics import calculate_binary_metrics, select_threshold_for_minimum_sensitivity
from training.nested_folds import (
    build_nested_partitions,
    load_official_subject_folds,
    official_fold_file_hashes,
    summarize_fold,
)
from training.pipeline import build_candidate_manifest
from training.runner import train_patient_equal_clip_epoch
from training.tb_screen_dataset import load_tb_screen_examples
from training.train import (
    DEFAULT_ELEVATED_SENSITIVITY,
    DEFAULT_HIGHER_SENSITIVITY,
    DEFAULT_MAX_CLIPS_PER_SUBJECT,
    PreparedPatient,
    _batches,
    _class_weights,
    _evaluate,
    _exclusion_summary,
    _ordered_thresholds,
    _prepare_examples,
    _resolve_device,
    _set_seed,
)


AUDIO_CONFIG = AudioFeatureConfig.tb_screen_reference()
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4


@dataclass(frozen=True)
class FitResult:
    state_dict: dict[str, Tensor]
    best_epoch: int
    validation: EvaluationResult


def _new_model(device: torch.device) -> ResidualSpectrogramClassifier:
    return ResidualSpectrogramClassifier(
        expected_n_mels=AUDIO_CONFIG.n_mels,
        expected_target_frames=AUDIO_CONFIG.target_frames,
    ).to(device)


def _training_batches(
    records: Sequence[PreparedPatient],
    *,
    batch_size: int,
    seed: int,
    epoch: int,
    use_augmentation: bool,
):
    shuffled = list(records)
    random.Random(seed + epoch).shuffle(shuffled)
    augmentation_rng = (
        np.random.default_rng(seed + epoch + 1) if use_augmentation else None
    )
    return _batches(
        shuffled,
        batch_size,
        AUDIO_CONFIG,
        augmentation_rng=augmentation_rng,
    )


def _fit_with_validation(
    train_records: Sequence[PreparedPatient],
    validation_records: Sequence[PreparedPatient],
    *,
    epochs: int,
    batch_size: int,
    seed: int,
    device: torch.device,
    use_augmentation: bool,
) -> FitResult:
    _set_seed(seed)
    model = _new_model(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )
    class_weights = _class_weights(train_records)
    validation_batches = _batches(
        validation_records,
        batch_size,
        AUDIO_CONFIG,
    )
    best_state: dict[str, Tensor] | None = None
    best_epoch = 0
    best_score = float("-inf")

    for epoch in range(epochs):
        loss = train_patient_equal_clip_epoch(
            model,
            optimizer,
            _training_batches(
                train_records,
                batch_size=batch_size,
                seed=seed,
                epoch=epoch,
                use_augmentation=use_augmentation,
            ),
            device=device,
            class_weights=class_weights,
        )
        validation = _evaluate(model, validation_batches, device=device)
        score = validation.metrics["auroc"]
        numeric_score = float(score) if score is not None else float("-inf")
        if numeric_score > best_score:
            best_score = numeric_score
            best_epoch = epoch + 1
            best_state = copy.deepcopy(model.state_dict())
        print(
            f"inner seed={seed} epoch={epoch + 1}/{epochs} "
            f"loss={loss:.4f} val_auc={score}",
            flush=True,
        )

    if best_state is None:
        raise RuntimeError("inner training produced no validation checkpoint")
    model.load_state_dict(best_state)
    validation = _evaluate(model, validation_batches, device=device)
    return FitResult(
        state_dict={name: value.detach().cpu() for name, value in best_state.items()},
        best_epoch=best_epoch,
        validation=validation,
    )


def _fit_fixed_epochs(
    train_records: Sequence[PreparedPatient],
    *,
    epochs: int,
    batch_size: int,
    seed: int,
    device: torch.device,
    use_augmentation: bool,
) -> ResidualSpectrogramClassifier:
    _set_seed(seed)
    model = _new_model(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )
    class_weights = _class_weights(train_records)
    for epoch in range(epochs):
        loss = train_patient_equal_clip_epoch(
            model,
            optimizer,
            _training_batches(
                train_records,
                batch_size=batch_size,
                seed=seed,
                epoch=epoch,
                use_augmentation=use_augmentation,
            ),
            device=device,
            class_weights=class_weights,
        )
        print(
            f"refit seed={seed} epoch={epoch + 1}/{epochs} loss={loss:.4f}",
            flush=True,
        )
    return model


def _selected_epoch(epochs: Sequence[int]) -> int:
    if not epochs or any(epoch < 1 for epoch in epochs):
        raise ValueError("selected epochs must be positive")
    return max(1, round(statistics.median(epochs)))


def _aggregate_operating_points(
    fold_metrics: Sequence[dict[str, float | int | None]],
) -> dict[str, float | int | None]:
    if not fold_metrics:
        raise ValueError("at least one fold metric is required")
    true_positive = sum(int(metrics["tp"] or 0) for metrics in fold_metrics)
    true_negative = sum(int(metrics["tn"] or 0) for metrics in fold_metrics)
    false_positive = sum(int(metrics["fp"] or 0) for metrics in fold_metrics)
    false_negative = sum(int(metrics["fn"] or 0) for metrics in fold_metrics)
    positive_count = true_positive + false_negative
    negative_count = true_negative + false_positive
    return {
        "sample_count": positive_count + negative_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "tp": true_positive,
        "tn": true_negative,
        "fp": false_positive,
        "fn": false_negative,
        "sensitivity": true_positive / positive_count if positive_count else None,
        "specificity": true_negative / negative_count if negative_count else None,
        "false_negative_rate": false_negative / positive_count if positive_count else None,
        "false_positive_rate": false_positive / negative_count if negative_count else None,
    }


def run_nested_cross_validation(
    folds: Sequence[Sequence[PatientExample]],
    *,
    fold_hashes: Sequence[str],
    output_dir: Path,
    epochs: int,
    batch_size: int,
    seed: int,
    device: torch.device,
    elevated_sensitivity: float,
    higher_sensitivity: float,
    use_augmentation: bool,
    excluded_subjects: Sequence[str],
) -> Path:
    if len(folds) < 3 or len(folds) != len(fold_hashes):
        raise ValueError("folds and hashes must describe at least three matching folds")
    if elevated_sensitivity < higher_sensitivity:
        raise ValueError("elevated sensitivity target must be at least the higher target")

    prepared_folds = tuple(
        _prepare_examples(fold, AUDIO_CONFIG, partition_name=f"fold-{index}")
        for index, fold in enumerate(folds)
    )
    nested_partitions = build_nested_partitions(prepared_folds)
    outer_reports: list[dict[str, object]] = []
    outer_labels: list[int] = []
    outer_probabilities: list[float] = []
    outer_epochs: list[int] = []
    outer_thresholds: list[dict[str, float]] = []
    outer_operating_points: dict[str, list[dict[str, float | int | None]]] = {
        "elevated": [],
        "higher": [],
    }

    for outer_index in range(len(prepared_folds)):
        outer_partitions = tuple(
            partition
            for partition in nested_partitions
            if partition.outer_fold == outer_index
        )
        outer_test = outer_partitions[0].test
        inner_labels: list[int] = []
        inner_probabilities: list[float] = []
        inner_epochs: list[int] = []
        inner_reports: list[dict[str, object]] = []
        for partition in outer_partitions:
            inner_index = partition.inner_fold
            inner_train = partition.train
            inner_validation = partition.validation
            run_seed = seed + outer_index * 100 + inner_index
            fit = _fit_with_validation(
                inner_train,
                inner_validation,
                epochs=epochs,
                batch_size=batch_size,
                seed=run_seed,
                device=device,
                use_augmentation=use_augmentation,
            )
            inner_labels.extend(fit.validation.labels)
            inner_probabilities.extend(fit.validation.probabilities)
            inner_epochs.append(fit.best_epoch)
            inner_reports.append(
                {
                    "inner_fold": inner_index,
                    "train": summarize_fold(inner_train),
                    "validation": summarize_fold(inner_validation),
                    "best_epoch": fit.best_epoch,
                    "validation_metrics": fit.validation.metrics,
                }
            )

        selected_epoch = _selected_epoch(inner_epochs)
        thresholds = _ordered_thresholds(
            select_threshold_for_minimum_sensitivity(
                inner_labels,
                inner_probabilities,
                elevated_sensitivity,
            ),
            select_threshold_for_minimum_sensitivity(
                inner_labels,
                inner_probabilities,
                higher_sensitivity,
            ),
        )
        outer_train = tuple(
            record
            for fold_index, fold in enumerate(prepared_folds)
            if fold_index != outer_index
            for record in fold
        )
        model = _fit_fixed_epochs(
            outer_train,
            epochs=selected_epoch,
            batch_size=batch_size,
            seed=seed + 10_000 + outer_index,
            device=device,
            use_augmentation=use_augmentation,
        )
        test_result = _evaluate(
            model,
            _batches(outer_test, batch_size, AUDIO_CONFIG),
            device=device,
        )
        test_operating_points = {
            name: calculate_binary_metrics(
                test_result.labels,
                test_result.probabilities,
                threshold,
            )
            for name, threshold in thresholds.items()
        }
        for name, metrics in test_operating_points.items():
            outer_operating_points[name].append(metrics)
        outer_labels.extend(test_result.labels)
        outer_probabilities.extend(test_result.probabilities)
        outer_epochs.append(selected_epoch)
        outer_thresholds.append(thresholds)
        outer_reports.append(
            {
                "outer_fold": outer_index,
                "outer_train": summarize_fold(outer_train),
                "outer_test": summarize_fold(outer_test),
                "inner_folds": inner_reports,
                "selection": {
                    "epoch": selected_epoch,
                    "thresholds": thresholds,
                    "pooled_inner_metrics": calculate_binary_metrics(
                        inner_labels,
                        inner_probabilities,
                    ),
                },
                "test": {
                    "metrics": test_result.metrics,
                    "operating_points": test_operating_points,
                },
            }
        )

    final_epoch = _selected_epoch(outer_epochs)
    final_thresholds = _ordered_thresholds(
        statistics.median(item["elevated"] for item in outer_thresholds),
        statistics.median(item["higher"] for item in outer_thresholds),
    )
    all_records = tuple(record for fold in prepared_folds for record in fold)
    final_model = _fit_fixed_epochs(
        all_records,
        epochs=final_epoch,
        batch_size=batch_size,
        seed=seed + 20_000,
        device=device,
        use_augmentation=use_augmentation,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "model-audio-residual.pt"
    torch.save(
        {name: value.detach().cpu() for name, value in final_model.state_dict().items()},
        artifact_path,
    )
    evaluation = {
        "protocol": {
            "id": "nested_official_subject_fivefold_v1",
            "unit": "subject",
            "outer_folds": len(folds),
            "inner_folds_per_outer": len(folds) - 1,
            "selection_metric": "auroc",
            "threshold_selection_split": "pooled_inner_validation",
            "seed": seed,
            "official_fold_csv_sha256": list(fold_hashes),
        },
        "outer_folds": outer_reports,
        "pooled_out_of_fold": {
            "metrics": calculate_binary_metrics(outer_labels, outer_probabilities),
            "operating_points": {
                name: _aggregate_operating_points(metrics)
                for name, metrics in outer_operating_points.items()
            },
        },
        "final_fit": {
            "subjects": len(all_records),
            "epoch": final_epoch,
            "thresholds": final_thresholds,
            "parameter_count": sum(
                parameter.numel() for parameter in final_model.parameters()
            ),
            "device": str(device),
            "learning_rate": LEARNING_RATE,
            "weight_decay": WEIGHT_DECAY,
            "augmentation": use_augmentation,
        },
        "excluded_subjects": _exclusion_summary(excluded_subjects),
        "limitations": [
            "Internal TBscreen cross-validation is not external validation.",
            "TBscreen labels are confounded with recruitment cohort.",
            "Threshold transfer is uncertain in small folds.",
        ],
    }
    metrics_path = output_dir / "metrics-audio-residual.json"
    metrics_path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    return build_candidate_manifest(
        artifact_path,
        output_dir / "manifest-audio-residual.json",
        model_name="SuaraNafas TBscreen residual audio CNN",
        model_version="3.0.0-research-candidate",
        input_mode="audio",
        metadata_dim=0,
        supported_countries=["KE"],
        preprocessing={"audio": AUDIO_CONFIG.to_manifest()},
        evaluation=evaluation,
        thresholds=final_thresholds,
        training_dataset="TBscreen passive cough official T1 subset",
        architecture=RESIDUAL_SPECTROGRAM_CNN_V2,
        initialization="random_pytorch_default",
        pretrained_weights=False,
        seed=seed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run strict nested patient-level CV for the residual audio CNN"
    )
    parser.add_argument("--passive-metadata", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--fold-directory", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("training-output-residual"),
    )
    parser.add_argument("--epochs", type=int, default=25)
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
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_clips_per_subject < 1:
        raise ValueError("epochs, batch-size, and max-clips-per-subject must be positive")

    examples = load_tb_screen_examples(
        (args.passive_metadata,),
        args.audio_root,
        max_clips=args.max_clips_per_subject,
    )
    available_subjects = {example.patient_id for example in examples}
    excluded_subjects = set(args.exclude_subject)
    if excluded_subjects - available_subjects:
        raise ValueError("excluded subject was not found in the dataset")
    examples = [
        example for example in examples if example.patient_id not in excluded_subjects
    ]
    fold_paths = tuple(args.fold_directory / f"T1_{index}.csv" for index in range(5))
    folds = load_official_subject_folds(fold_paths, examples)
    manifest_path = run_nested_cross_validation(
        folds,
        fold_hashes=official_fold_file_hashes(fold_paths),
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
        device=_resolve_device(args.device),
        elevated_sensitivity=args.elevated_sensitivity,
        higher_sensitivity=args.higher_sensitivity,
        use_augmentation=not args.no_augmentation,
        excluded_subjects=tuple(excluded_subjects),
    )
    print(f"saved blocked residual candidate: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
