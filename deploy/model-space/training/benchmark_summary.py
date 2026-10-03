"""Summarize paired, subject-level OOF reports without loading or training models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score

V3 = "residual_fusion_cnn_v3"
SOURCES = {
    "cnn-reports.json": (V3, "residual_tabular_fusion_v4"),
    "head-reports.json": ("ast_audio", "clinical_only", "ast_clinical"),
}
MODELS = tuple(model for models in SOURCES.values() for model in models)
SEED = 2026
DEFAULT_BOOTSTRAP = 2000
CI_SCOPE = (
    "95% percentile intervals conditional on fixed OOF predictions; not external "
    "validation and not repeated-training uncertainty. No significance claim is made."
)


def _vector(oof: dict, field: str) -> np.ndarray:
    values = oof.get(field)
    if not isinstance(values, list) or not values:
        raise ValueError(f"OOF {field} must be a non-empty numeric vector")
    if field in ("indices", "folds") and any(type(value) is not int for value in values):
        raise ValueError(f"OOF {field} must contain integers, not booleans")
    try:
        array = np.asarray(values)
    except (ValueError, TypeError):
        raise ValueError(f"OOF {field} must be a numeric vector") from None
    if array.ndim != 1 or array.dtype.kind not in "biuf" or not np.isfinite(array).all():
        raise ValueError(f"OOF {field} must be a finite numeric vector")
    return array


def _validate_oof(report: dict) -> dict:
    if not isinstance(report, dict) or not isinstance(report.get("oof"), dict):
        raise ValueError("every model requires an OOF object")
    fields = ("indices", "folds", "labels", "probabilities", "predictions", "thresholds")
    oof = {field: _vector(report["oof"], field) for field in fields}
    size = len(oof["indices"])
    if any(len(array) != size for array in oof.values()):
        raise ValueError("OOF vectors must have equal lengths")
    if not np.array_equal(np.sort(oof["indices"]), np.arange(size)):
        raise ValueError("OOF indices must cover [0, subject count) exactly once")
    if (oof["folds"] < 0).any():
        raise ValueError("OOF folds must be non-negative")
    for field in ("labels", "predictions"):
        if not np.isin(oof[field], [0, 1]).all():
            raise ValueError(f"OOF {field} must be binary")
    for field in ("probabilities", "thresholds"):
        if ((oof[field] < 0) | (oof[field] > 1)).any():
            raise ValueError(f"OOF {field} must be in [0, 1]")
    if not np.array_equal(oof["predictions"], oof["probabilities"] >= oof["thresholds"]):
        raise ValueError("OOF predictions must equal probabilities >= thresholds exactly")
    _validate_folds(report.get("folds"), oof)
    return oof


def _validate_folds(reports: list, oof: dict) -> None:
    if not isinstance(reports, list) or len(reports) < 2:
        raise ValueError("at least two fold reports are required")
    if any(not isinstance(row, dict) or type(row.get("fold")) is not int for row in reports):
        raise ValueError("fold reports require integer fold numbers")
    folds = [row["fold"] for row in reports]
    if len(set(folds)) != len(folds) or set(folds) != set(oof["folds"]):
        raise ValueError("fold reports must match OOF folds exactly once")
    for row in reports:
        mask = oof["folds"] == row["fold"]
        labels = oof["labels"][mask]
        if set(labels) != {0, 1}:
            raise ValueError("every test fold must contain both labels")
        counts = {"sample_count": len(labels), "positive_count": int(labels.sum()),
                  "negative_count": int((labels == 0).sum())}
        if any(type(row.get(key)) is not int or row[key] != count for key, count in counts.items()):
            raise ValueError("fold test counts must match OOF labels and membership")
        threshold = row.get("threshold")
        if type(threshold) not in (int, float) or not np.isfinite(threshold):
            raise ValueError("fold threshold must be finite and numeric")
        if not np.all(oof["thresholds"][mask] == threshold):
            raise ValueError("OOF thresholds must equal the locked fold threshold")


def _aligned_oof(reports: dict) -> dict:
    if not isinstance(reports, dict) or set(reports) != set(MODELS):
        raise ValueError("reports must contain exactly the five benchmark models")
    oofs = {name: _validate_oof(reports[name]) for name in MODELS}
    reference = oofs[V3]
    for oof in oofs.values():
        if any(not np.array_equal(oof[field], reference[field])
               for field in ("indices", "labels", "folds")):
            raise ValueError("OOF indices, labels and folds must be exactly aligned across models")
    return oofs


def _metrics(oof: dict, selection) -> dict:
    labels, probabilities, flags = (oof[field][selection] for field in
                                   ("labels", "probabilities", "predictions"))
    tn, fp, fn, tp = (int(value) for value in confusion_matrix(labels, flags, labels=[0, 1]).ravel())
    return {
        "auroc": float(roc_auc_score(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "sensitivity": tp / (tp + fn), "specificity": tn / (tn + fp),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "sample_count": len(labels), "positive_count": tp + fn, "negative_count": tn + fp,
    }


def _subject_resamples(oof: dict, bootstrap: int):
    strata = [np.flatnonzero((oof["folds"] == fold) & (oof["labels"] == label))
              for fold in np.unique(oof["folds"]) for label in (0, 1)]
    rng = np.random.default_rng(SEED)
    for _ in range(bootstrap):
        yield np.concatenate([rng.choice(group, size=len(group), replace=True) for group in strata])


def _percentile_ci(values: np.ndarray) -> list[float]:
    return np.percentile(values, [2.5, 97.5], method="linear").tolist()


def _model_summary(oof: dict, bootstrap_aucs: np.ndarray) -> dict:
    folds = [{"fold": int(fold), **_metrics(oof, oof["folds"] == fold)}
             for fold in np.unique(oof["folds"])]
    aucs = [fold["auroc"] for fold in folds]
    return {
        "pooled_metrics": _metrics(oof, slice(None)),
        "auroc_ci95": _percentile_ci(bootstrap_aucs), "folds": folds,
        "fold_auroc_mean": float(np.mean(aucs)), "fold_auroc_std": float(np.std(aucs, ddof=1)),
        "fold_auroc_std_ddof": 1,
    }


def summarize(reports: dict, *, bootstrap: int = DEFAULT_BOOTSTRAP) -> dict:
    """Compute aggregates only; >=20 draws enable small tests, CLI requires >=1000."""
    if type(bootstrap) is not int or bootstrap < 20:
        raise ValueError("bootstrap must be an integer >= 20 (CLI requires >= 1000)")
    oofs = _aligned_oof(reports)
    reference = oofs[V3]
    draws = np.empty((bootstrap, len(MODELS)))
    for row, selection in enumerate(_subject_resamples(reference, bootstrap)):
        for column, oof in enumerate(oofs.values()):
            draws[row, column] = roc_auc_score(oof["labels"][selection], oof["probabilities"][selection])
    models = {name: _model_summary(oofs[name], draws[:, column]) for column, name in enumerate(MODELS)}
    deltas = {}
    for name in ("ast_clinical", "clinical_only"):
        deltas[f"{name}_minus_v3"] = {
            "model": name, "reference": V3,
            "auroc_delta": models[name]["pooled_metrics"]["auroc"] - models[V3]["pooled_metrics"]["auroc"],
            "auroc_delta_ci95": _percentile_ci(draws[:, MODELS.index(name)] - draws[:, MODELS.index(V3)]),
        }
    return {
        "sources": list(SOURCES),
        "cohort": {"sample_count": len(reference["labels"]),
                   "positive_count": int(reference["labels"].sum()),
                   "negative_count": int((reference["labels"] == 0).sum()),
                   "fold_count": len(np.unique(reference["folds"]))},
        "validation": {"exact_oof_alignment": True, "each_subject_tested_once": True},
        "bootstrap": {"resamples": bootstrap, "seed": SEED, "unit": "subject",
                      "strata": ["fold", "label"], "paired_across_models": True,
                      "confidence_level": 0.95, "method": "percentile", "quantile_method": "linear",
                      "scope": CI_SCOPE},
        "notes": ["Sensitivity/specificity use locked per-fold validation thresholds; no test retuning.",
                  "Fold AUROC mean is unweighted; sample std uses ddof=1 and is descriptive, not a CI.",
                  "Pooled AUROC compares scores across folds; fold score calibration can change rankings."],
        "models": models, "paired_deltas": deltas,
    }


def _load_reports(output_dir: Path) -> dict:
    reports = {}
    for filename, models in SOURCES.items():
        with (output_dir / filename).open(encoding="utf-8") as stream:
            source = json.load(stream)
        if not isinstance(source, dict) or set(source) != set(models):
            raise ValueError(f"{filename} must contain its expected benchmark models")
        reports.update(source)
    return reports


def _print_table(summary: dict) -> None:
    print("Model                         AUROC [95% CI]       Fold mean +/- SD   AP     Brier  Sens   Spec   TP TN FP FN")
    for name, model in summary["models"].items():
        metrics, (lower, upper) = model["pooled_metrics"], model["auroc_ci95"]
        print(f"{name:29} {metrics['auroc']:.4f} [{lower:.4f}, {upper:.4f}] "
              f"{model['fold_auroc_mean']:.4f} +/- {model['fold_auroc_std']:.4f} "
              f"{metrics['average_precision']:.4f} {metrics['brier_score']:.4f} "
              f"{metrics['sensitivity']:.4f} {metrics['specificity']:.4f} "
              f"{metrics['tp']} {metrics['tn']} {metrics['fp']} {metrics['fn']}")
    for name, delta in summary["paired_deltas"].items():
        lower, upper = delta["auroc_delta_ci95"]
        print(f"{name}: paired AUROC delta {delta['auroc_delta']:+.4f} [{lower:+.4f}, {upper:+.4f}]")
    print(CI_SCOPE)
    print("\n".join(summary["notes"]))


def _cli_bootstrap(value: str) -> int:
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("bootstrap must be an integer >= 1000") from None
    if count < 1000:
        raise argparse.ArgumentTypeError("bootstrap must be an integer >= 1000")
    return count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=_cli_bootstrap, default=DEFAULT_BOOTSTRAP)
    args = parser.parse_args(argv)
    destination = args.output_dir / "summary.json"
    if destination.exists():
        parser.error("summary.json already exists; refusing to overwrite")
    try:
        summary = summarize(_load_reports(args.output_dir), bootstrap=args.bootstrap)
        payload = json.dumps(summary, indent=2, allow_nan=False) + "\n"
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    _print_table(summary)


if __name__ == "__main__":
    main()
