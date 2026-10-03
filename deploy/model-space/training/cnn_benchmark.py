"""Fresh v3/v4 fits on supplied patient-disjoint outer folds; no final checkpoints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
    roc_curve,
)

from src.audio_features import AudioFeatureConfig
from src.model import RESIDUAL_FUSION_CNN_V3, RESIDUAL_TABULAR_FUSION_V4
from training.cross_validate_fusion import (
    FusionPatient,
    _fit,
    _new_fusion_model,
    _predict,
    _prepare_examples,
)
from training.dataset import PatientExample, _spread_sample
from training.encoding import ClinicalPreprocessor
from training.train import _resolve_device


ARCHITECTURES = (RESIDUAL_FUSION_CNN_V3, RESIDUAL_TABULAR_FUSION_V4)
SPLITS = ("train", "validation", "test")
MAX_CLIPS = 8
THRESHOLD_NOTE = (
    "Largest finite validation ROC threshold attaining sensitivity >= 0.90; "
    "positive means probability >= threshold. Test sensitivity is not guaranteed. "
    "Pooled sensitivity/specificity use each subject's locked fold threshold, "
    "never a threshold selected on pooled test labels."
)


def _validate_partitions(examples: Sequence[PatientExample], partitions: list[dict]) -> None:
    identifiers = [example.patient_id for example in examples]
    if not examples or not partitions:
        raise ValueError("examples and partitions must be non-empty")
    if any(not isinstance(value, str) or not value for value in identifiers):
        raise ValueError("patient IDs must be non-empty strings")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("patient IDs must be unique")
    if any(example.label not in (0, 1) for example in examples):
        raise ValueError("labels must be binary")
    if any(not example.audio_paths for example in examples):
        raise ValueError("every subject must have audio clips")
    test_counts = np.zeros(len(examples), dtype=int)
    fold_numbers: set[int] = set()
    for partition in partitions:
        fold = partition["fold"]
        if isinstance(fold, bool) or not isinstance(fold, (int, np.integer)) or fold < 0:
            raise ValueError("fold numbers must be non-negative integers")
        if fold in fold_numbers:
            raise ValueError("fold numbers must be unique")
        fold_numbers.add(int(fold))
        seen_ids: set[str] = set()
        for split in SPLITS:
            indices = partition[split]
            if any(isinstance(i, bool) or not isinstance(i, (int, np.integer))
                   or not 0 <= int(i) < len(examples) for i in indices):
                raise ValueError("partition indices must be in-range integers")
            split_ids = {identifiers[i] for i in indices}
            if len(split_ids) != len(indices):
                raise ValueError("duplicate subjects within a split")
            if seen_ids & split_ids:
                raise ValueError("train, validation and test patient IDs must be disjoint")
            seen_ids.update(split_ids)
            if {examples[i].label for i in indices} != {0, 1}:
                raise ValueError("every split must contain both classes")
        test_counts[partition["test"]] += 1
    if not np.all(test_counts == 1):
        raise ValueError("partitions must provide exactly one test prediction per subject")


def _validation_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    _, sensitivity, thresholds = roc_curve(labels, probabilities, drop_intermediate=False)
    eligible = thresholds[np.isfinite(thresholds) & (sensitivity >= 0.90)]
    if not len(eligible):
        raise ValueError("no finite validation threshold attains 90% sensitivity")
    return float(eligible.max())


def _metrics(labels: np.ndarray, probabilities: np.ndarray, flags: np.ndarray) -> dict:
    positive = labels == 1
    return {
        "auroc": float(roc_auc_score(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "sensitivity": float(flags[positive].mean()),
        "specificity": float((~flags[~positive]).mean()),
        "sample_count": len(labels),
        "positive_count": int(positive.sum()),
        "negative_count": int((~positive).sum()),
    }


def _checked_predict(state: dict, patients: Sequence[FusionPatient], **kwargs) -> tuple:
    # The shared helper returns (labels, probabilities), in patient/batch order.
    labels, probabilities = _predict(state, patients, **kwargs)
    labels, probabilities = np.asarray(labels), np.asarray(probabilities, dtype=float)
    expected = np.asarray([patient.label for patient in patients])
    if not np.array_equal(labels, expected) or probabilities.shape != expected.shape:
        raise ValueError("prediction labels/order or count do not match the split")
    if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("predictions must be finite probabilities in [0, 1]")
    return labels, probabilities


def benchmark_cnns(
    examples: Sequence[PatientExample],
    partitions: list[dict],
    output_dir: Path,
    *,
    epochs: int = 8,
    batch_size: int = 16,
    seed: int = 42,
    device: str = "cuda",
) -> dict:
    """Return architecture-keyed reports; OOF arrays follow input example order.

    Each fold dict supplies zero-based indices under train/validation/test and
    a unique non-negative fold number. Both architectures use seed + fold,
    train-only clinical statistics and the same deterministic eight-clip cap.
    Weights are CPU state dicts; their clinical preprocessor is in the fold report.
    """
    _validate_partitions(examples, partitions)
    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch_size must be positive")
    resolved_device = _resolve_device(device)
    audio_config = AudioFeatureConfig()
    examples = [
        replace(example, audio_paths=tuple(_spread_sample(example.audio_paths, MAX_CLIPS)))
        for example in examples
    ]
    clip_cache: dict[Path, np.ndarray] = {}
    labels = np.asarray([example.label for example in examples], dtype=int)
    oof_probabilities = {name: np.full(len(examples), np.nan) for name in ARCHITECTURES}
    oof_flags = {name: np.zeros(len(examples), dtype=bool) for name in ARCHITECTURES}
    oof_thresholds = {name: np.full(len(examples), np.nan) for name in ARCHITECTURES}
    oof_folds = np.full(len(examples), -1, dtype=int)
    reports = {name: {"folds": [], "threshold_note": THRESHOLD_NOTE} for name in ARCHITECTURES}

    for partition in partitions:
        fold = int(partition["fold"])
        print(f"CNN fold={fold}: preparing shared audio and train-only clinical data", flush=True)
        preprocessor = ClinicalPreprocessor.fit(
            [examples[i].metadata for i in partition["train"]]
        )
        prepared = {
            split: _prepare_examples(
                [examples[i] for i in partition[split]], preprocessor, audio_config,
                partition_name=f"fold-{fold}-{split}", cache=clip_cache,
            )
            for split in SPLITS
        }
        test_indices = partition["test"]
        oof_folds[test_indices] = fold
        for architecture in ARCHITECTURES:
            print(f"CNN model={architecture} fold={fold} seed={seed + fold}: fitting", flush=True)
            state, selected_epoch = _fit(
                prepared["train"], prepared["validation"], epochs=epochs,
                batch_size=batch_size, seed=seed + fold, device=resolved_device,
                audio_config=audio_config, architecture=architecture,
                false_negative_penalty=1.0, spec_augment_enabled=False,
                distillation_weight=0.0,
            )
            if not 1 <= selected_epoch <= epochs:
                raise ValueError("selected epoch must be within the requested training budget")
            state = {name: value.detach().cpu() for name, value in state.items()}
            predict_options = {
                "batch_size": batch_size, "audio_config": audio_config,
                "device": resolved_device, "architecture": architecture,
            }
            validation_labels, validation_probs = _checked_predict(
                state, prepared["validation"], **predict_options,
            )
            threshold = _validation_threshold(validation_labels, validation_probs)
            test_labels, test_probs = _checked_predict(state, prepared["test"], **predict_options)
            if np.isfinite(oof_probabilities[architecture][test_indices]).any():
                raise ValueError("duplicate OOF predictions")
            flags = test_probs >= threshold
            oof_probabilities[architecture][test_indices] = test_probs
            oof_flags[architecture][test_indices] = flags
            oof_thresholds[architecture][test_indices] = threshold
            checkpoint = Path(output_dir) / architecture / f"fold-{fold}" / "weights.pt"
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(state, checkpoint)
            report = reports[architecture]
            if "param_count" not in report:
                model = _new_fusion_model(
                    prepared["train"][0].clinical.shape[0], audio_config,
                    torch.device("cpu"), architecture,
                )
                report["param_count"] = sum(parameter.numel() for parameter in model.parameters())
                del model
            report["folds"].append({
                "fold": fold, "seed": int(seed + fold),
                **_metrics(test_labels, test_probs, flags),
                "train_subjects": len(prepared["train"]),
                "validation_subjects": len(prepared["validation"]),
                "validation_auc": float(roc_auc_score(validation_labels, validation_probs)),
                "threshold": threshold, "selected_epoch": int(selected_epoch),
                "checkpoint_path": str(checkpoint),
                "clinical_preprocessor": preprocessor.to_dict(),
            })

    for architecture, report in reports.items():
        probabilities, flags = oof_probabilities[architecture], oof_flags[architecture]
        if not np.isfinite(probabilities).all():
            raise ValueError("missing OOF predictions")
        report["pooled_metrics"] = _metrics(labels, probabilities, flags)
        report["oof"] = {
            "indices": list(range(len(examples))), "folds": oof_folds.tolist(),
            "labels": labels.tolist(), "probabilities": probabilities.tolist(),
            "predictions": flags.tolist(), "thresholds": oof_thresholds[architecture].tolist(),
        }
    return reports
