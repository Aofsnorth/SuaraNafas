"""Regularized patient-level heads on frozen AST features; no encoder training."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

from training.ast_features import EMBEDDING_DIM
from training.cnn_benchmark import (
    THRESHOLD_NOTE,
    _metrics,
    _validate_partitions,
    _validation_threshold,
)
from training.dataset import PatientExample
from training.encoding import ClinicalPreprocessor

ARCHITECTURE = "frozen_ast_linear_v1"
MODES = ("ast_audio", "clinical_only", "ast_clinical")
L2_GRID = (0.001, 0.01, 0.1)
SCALE_FLOOR = 1e-6


def _cpu_tensor(value, name: str) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        if value.is_complex():
            raise ValueError(f"{name} must be real numeric values")
        tensor = value.detach().to(device="cpu", dtype=torch.float32)
    else:
        array = np.asarray(value)
        if array.dtype.kind not in "biuf":
            raise ValueError(f"{name} must be real numeric values")
        tensor = torch.tensor(np.array(array, copy=True), dtype=torch.float32)
    if not torch.isfinite(tensor).all():
        raise ValueError(f"{name} must contain only finite values")
    return tensor


def _matrix(value, name: str) -> torch.Tensor:
    tensor = _cpu_tensor(value, name)
    if tensor.ndim != 2 or min(tensor.shape) < 1:
        raise ValueError(f"{name} must have non-empty shape (patients, features)")
    return tensor


def _labels(value, rows: int, name: str) -> torch.Tensor:
    tensor = _cpu_tensor(value, name)
    if tensor.shape != (rows,):
        raise ValueError(f"{name} must have shape ({rows},)")
    if set(tensor.tolist()) != {0.0, 1.0}:
        raise ValueError(f"{name} must be binary and contain both classes")
    return tensor


def _device(requested) -> torch.device:
    device = torch.device(requested)
    if device.type not in {"cpu", "cuda"}:
        raise ValueError("head device must be cpu, cuda, or cuda:N")
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable; use device='cpu' explicitly")
        if device.index is not None and device.index >= torch.cuda.device_count():
            raise ValueError("requested CUDA device is unavailable")
    return device


def _validate_options(epochs, l2, seed) -> None:
    if isinstance(epochs, bool) or not isinstance(epochs, (int, np.integer)) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if not np.isfinite(l2) or l2 < 0:
        raise ValueError("l2 must be finite and non-negative")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or not 0 <= seed < 2**63:
        raise ValueError("seed must be a non-negative integer below 2**63")


def _fit_scaler(features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    mean = features.double().mean(dim=0).float()
    scale = features.double().std(dim=0, correction=0).clamp_min(SCALE_FLOOR).float()
    return mean, scale


def _standardize(features, mean, scale) -> torch.Tensor:
    # Double intermediates avoid overflow when subtracting large finite inputs.
    return _cpu_tensor((features.double() - mean) / scale, "normalized features")


def fit_head(
    train_x, train_y, validation_x, validation_y, *, epochs=120, l2=0.01,
    seed=42, device: str | torch.device = "cuda", log_prefix="head",
) -> dict:
    """Fit full-batch Linear(d, 1) with unweighted BCE + l2 * sum(weight**2).

    The bias is unpenalized. Population mean/std use training rows only, with
    std floored at 1e-6. Select by validation AUROC, then lower unweighted BCE;
    exact ties retain the earlier epoch. Return detached, weights-only-safe CPU
    tensors (weight shape (1, d), bias (1,)); no test inputs are accepted.
    """
    _validate_options(epochs, l2, seed)
    train_x, validation_x = _matrix(train_x, "train_x"), _matrix(validation_x, "validation_x")
    if train_x.shape[1] != validation_x.shape[1]:
        raise ValueError("training and validation feature dimensions must match")
    train_y = _labels(train_y, len(train_x), "train_y")
    validation_y = _labels(validation_y, len(validation_x), "validation_y")
    resolved = _device(device)
    mean, scale = _fit_scaler(train_x)
    train = _standardize(train_x, mean, scale).to(resolved)
    validation = _standardize(validation_x, mean, scale).to(resolved)
    target, validation_target = train_y.to(resolved), validation_y.to(resolved)
    torch.manual_seed(int(seed))
    model = torch.nn.Linear(train.shape[1], 1).to(resolved)
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    best, best_key = {}, (-float("inf"), -float("inf"))
    for epoch in range(1, int(epochs) + 1):
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(train).squeeze(1), target) + l2 * model.weight.square().sum()
        if not torch.isfinite(loss):
            raise ValueError("head training loss must be finite")
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            logits = model(validation).squeeze(1)
            validation_bce = float(criterion(logits, validation_target).item())
            if not torch.isfinite(logits).all() or not np.isfinite(validation_bce):
                raise ValueError("head validation logits and loss must be finite")
            auc = float(roc_auc_score(validation_y.numpy(), logits.sigmoid().cpu().numpy()))
        if (auc, -validation_bce) > best_key:
            best_key = (auc, -validation_bce)
            best = {
                "mean": mean.clone(), "scale": scale.clone(),
                "weight": model.weight.detach().cpu().clone(),
                "bias": model.bias.detach().cpu().clone(), "input_dim": int(train.shape[1]),
                "selected_epoch": epoch, "l2": float(l2), "validation_auc": auc,
                "validation_bce": validation_bce, "architecture": ARCHITECTURE,
            }
        if epoch % 10 == 0 or epoch == epochs:
            print(f"{log_prefix} epoch={epoch}/{epochs} loss={loss.item():.6f} "
                  f"val_auc={auc:.6f} val_bce={validation_bce:.6f}", flush=True)
    return best


def refit_head(
    train_x, train_y, *, epochs: int, l2: float, seed=42,
    device: str | torch.device = "cuda",
) -> dict:
    """Fit all supplied development rows for fixed, caller-selected CV settings.

    Uses the same initialization, normalization and unweighted BCE plus
    l2 * sum(weight**2) as fit_head. Return the final epoch as a CPU checkpoint
    compatible with predict_head; no validation/test selection or evaluation
    occurs, and this artifact supplies no evidence of held-out performance.
    """
    _validate_options(epochs, l2, seed)
    train_x = _matrix(train_x, "train_x")
    train_y = _labels(train_y, len(train_x), "train_y")
    resolved = _device(device)
    mean, scale = _fit_scaler(train_x)
    train = _standardize(train_x, mean, scale).to(resolved)
    target = train_y.to(resolved)
    torch.manual_seed(int(seed))
    model = torch.nn.Linear(train.shape[1], 1).to(resolved)
    criterion = torch.nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    for epoch in range(1, int(epochs) + 1):
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(train).squeeze(1), target) + l2 * model.weight.square().sum()
        if not torch.isfinite(loss):
            raise ValueError("head training loss must be finite")
        loss.backward()
        optimizer.step()
        if epoch % 10 == 0 or epoch == epochs:
            print(f"head-refit epoch={epoch}/{epochs} loss={loss.item():.6f}", flush=True)
    return {
        "mean": mean.clone(), "scale": scale.clone(),
        "weight": _cpu_tensor(model.weight, "refit weight").clone(),
        "bias": _cpu_tensor(model.bias, "refit bias").clone(),
        "input_dim": int(train.shape[1]), "l2": float(l2), "selected_epoch": int(epochs),
        "architecture": ARCHITECTURE, "fit_strategy": "fixed_epochs_full_development_cohort",
    }


def predict_head(checkpoint: dict, x, *, device: str | torch.device = "cpu") -> np.ndarray:
    """Return finite probabilities with shape (patients,) using saved statistics.

    Pass a checkpoint dict, e.g. loaded with torch.load(..., map_location='cpu',
    weights_only=True). Empty, nonfinite and dimension-mismatched inputs fail.
    """
    features = _matrix(x, "x")
    dimension = checkpoint.get("input_dim")
    if type(dimension) is not int or dimension < 1 or features.shape[1] != dimension:
        raise ValueError("x feature dimension must match checkpoint input_dim")
    state = {}
    for name, shape in (("mean", (dimension,)), ("scale", (dimension,)),
                        ("weight", (1, dimension)), ("bias", (1,))):
        if name not in checkpoint:
            raise ValueError(f"checkpoint is missing {name}")
        state[name] = _cpu_tensor(checkpoint[name], f"checkpoint {name}")
        if state[name].shape != shape:
            raise ValueError(f"checkpoint {name} must have shape {shape}")
    if torch.any(state["scale"] < SCALE_FLOOR):
        raise ValueError("checkpoint scale must be at least 1e-6")
    normalized = _standardize(features, state["mean"], state["scale"])
    resolved = _device(device)
    with torch.inference_mode():
        logits = torch.nn.functional.linear(
            normalized.to(resolved), state["weight"].to(resolved), state["bias"].to(resolved),
        ).squeeze(1)
        if not torch.isfinite(logits).all():
            raise ValueError("prediction logits must be finite")
        return logits.sigmoid().cpu().numpy()


def _select_head(train_x, train_y, validation_x, validation_y, **options) -> dict:
    best = {}
    prefix = options.pop("log_prefix")
    for l2 in L2_GRID:
        candidate = fit_head(train_x, train_y, validation_x, validation_y, l2=l2,
                             log_prefix=f"{prefix} l2={l2}", **options)
        # Across penalties use AUROC only; a tie retains the first grid value.
        if not best or candidate["validation_auc"] > best["validation_auc"]:
            best = candidate
    return best


def benchmark_heads(
    examples: Sequence[PatientExample], embeddings, partitions: list[dict], output_dir: Path,
    *, epochs=120, seed=42, device="cuda",
) -> dict:
    """Return CNN-schema reports for audio, all 27 clinical features, and fusion.

    Embeddings from ast_features must follow example order. Fold heads are saved
    without a full-data refit and can form a research ensemble for new subjects.
    Reported OOF metrics use individual held-out heads, NEVER that ensemble.
    Per-fold report.json files are durable; the parent CLI saves aggregate reports.
    """
    _validate_partitions(examples, partitions)
    _validate_options(epochs, L2_GRID[0], seed)
    resolved = _device(device)
    audio = _matrix(embeddings, "embeddings").numpy()
    if audio.shape != (len(examples), EMBEDDING_DIM):
        raise ValueError(f"embeddings must have shape ({len(examples)}, {EMBEDDING_DIM})")
    labels = np.asarray([example.label for example in examples], dtype=int)
    reports = {mode: {"folds": [], "threshold_note": THRESHOLD_NOTE} for mode in MODES}
    probabilities = {mode: np.full(len(examples), np.nan) for mode in MODES}
    thresholds = {mode: np.full(len(examples), np.nan) for mode in MODES}
    oof_folds = np.full(len(examples), -1, dtype=int)
    for partition in partitions:
        fold = int(partition["fold"])
        train, validation, test = (partition[name] for name in ("train", "validation", "test"))
        preprocessor = ClinicalPreprocessor.fit([examples[i].metadata for i in train])
        clinical = _matrix(np.stack([
            preprocessor.transform(example.metadata, cough_count=len(example.audio_paths))
            for example in examples
        ]), "clinical features").numpy()
        inputs = dict(zip(MODES, (audio, clinical, np.concatenate((audio, clinical), axis=1))))
        oof_folds[test] = fold
        for mode, features in inputs.items():
            prefix = f"AST mode={mode} fold={fold}"
            print(f"{prefix}: selecting regularization on validation only", flush=True)
            state = _select_head(features[train], labels[train], features[validation], labels[validation],
                                 epochs=epochs, seed=seed + fold, device=resolved, log_prefix=prefix)
            validation_probs = predict_head(state, features[validation], device=resolved)
            threshold = _validation_threshold(labels[validation], validation_probs)
            test_probs = predict_head(state, features[test], device=resolved)
            if np.isfinite(probabilities[mode][test]).any():
                raise ValueError("duplicate OOF predictions")
            probabilities[mode][test], thresholds[mode][test] = test_probs, threshold
            state.update({"architecture": ARCHITECTURE, "input_mode": mode,
                          "clinical_preprocessor": preprocessor.to_dict(),
                          "threshold": threshold, "fold": fold, "seed": int(seed + fold)})
            checkpoint = Path(output_dir) / mode / f"fold-{fold}" / "head.pt"
            fold_report = {
                "fold": fold, "seed": int(seed + fold),
                **_metrics(labels[test], test_probs, test_probs >= threshold),
                "train_subjects": len(train), "validation_subjects": len(validation),
                "validation_auc": float(state["validation_auc"]), "threshold": threshold,
                "selected_l2": float(state["l2"]), "selected_epoch": int(state["selected_epoch"]),
                "checkpoint_path": str(checkpoint), "clinical_preprocessor": preprocessor.to_dict(),
            }
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(state, checkpoint)
            checkpoint.with_name("report.json").write_text(
                json.dumps(fold_report, indent=2, allow_nan=False), encoding="utf-8",
            )
            reports[mode]["folds"].append(fold_report)
            reports[mode]["param_count"] = int(features.shape[1] + 1)
            print(f"{prefix} selected_l2={state['l2']} epoch={state['selected_epoch']} "
                  f"val_auc={state['validation_auc']:.6f} test_auc={fold_report['auroc']:.6f}", flush=True)
    for mode, report in reports.items():
        probs, cutoffs = probabilities[mode], thresholds[mode]
        if not np.isfinite(probs).all() or not np.isfinite(cutoffs).all() or (oof_folds < 0).any():
            raise ValueError("missing OOF predictions or thresholds")
        flags = probs >= cutoffs
        report["pooled_metrics"] = _metrics(labels, probs, flags)
        report["oof"] = {
            "indices": list(range(len(examples))), "folds": oof_folds.tolist(),
            "labels": labels.tolist(), "probabilities": probs.tolist(),
            "predictions": flags.tolist(), "thresholds": cutoffs.tolist(),
        }
    return reports
