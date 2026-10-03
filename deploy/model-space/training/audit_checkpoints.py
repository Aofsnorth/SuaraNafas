"""Read-only audit (stdlib + torch): python -m training.audit_checkpoints --root ROOT --output NEW_FILE."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from pickle import UnpicklingError

import torch
from src.model import build_screening_model

METRICS = ("auroc", "average_precision", "brier_score", "sample_count", "positive_count", "negative_count",
    "threshold", "true_positive", "true_negative", "false_positive", "false_negative", "tp", "tn", "fp", "fn",
    "sensitivity", "recall", "specificity", "false_negative_rate", "false_positive_rate", "fnr", "fpr",
    "precision", "negative_predictive_value", "npv")
PARTITIONS = ("train", "validation", "test")


def subject_summary(evaluation: dict) -> dict:
    folds = evaluation.get("folds", [])
    if "patient_ids" not in evaluation or not folds or any(
        f"{part}_patient_ids" not in fold for fold in folds for part in PARTITIONS):
        return {"status": "membership_unavailable"}
    pooled = Counter(evaluation["patient_ids"])
    unions = {part: set() for part in PARTITIONS}
    tests, overlaps = Counter(), []
    for index, fold in enumerate(folds):
        members = {part: set(fold[f"{part}_patient_ids"]) for part in PARTITIONS}
        tests.update(fold["test_patient_ids"])
        for part in PARTITIONS:
            unions[part].update(members[part])
        overlaps.append({"fold_index": index, **{
            f"{left}_{right}": len(members[left] & members[right])
            for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))
        }})
    return {"pooled_entries": pooled.total(), "pooled_unique_subjects": len(pooled),
        "pooled_repeated_entries": pooled.total() - len(pooled),
        "pooled_repeated_subjects": sum(count > 1 for count in pooled.values()),
        "fold_union_subjects": {part: len(subjects) for part, subjects in unions.items()},
        "all_fold_unique_subjects": len(set().union(*unions.values())),
        "test_entries": tests.total(), "repeated_test_entries": tests.total() - len(tests),
        "repeated_test_subjects": sum(count > 1 for count in tests.values()),
        "within_fold_overlap": overlaps,
        "sample_count_is_not_unique": evaluation.get("pooled_metrics", {}).get("sample_count") != len(pooled)}


def check_checkpoint(path: Path, manifest: dict, result: dict) -> None:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    expected = manifest.get("artifact_sha256", "").lower()
    result["integrity"] = {"status": "verified" if actual == expected else "mismatch",
                           "expected_sha256": expected, "actual_sha256": actual}
    audio = manifest["preprocessing"]["audio"]
    dimensions = (audio["n_mels"], audio["target_frames"], manifest["metadata_dim"])
    if any(type(size) is not int or size < 0 for size in dimensions) or not all(dimensions[:2]):
        raise ValueError("invalid model dimensions")
    model = build_screening_model(manifest["architecture"], metadata_dim=dimensions[2],
        input_mode=manifest["input_mode"], expected_n_mels=dimensions[0], expected_target_frames=dimensions[1])
    model.load_state_dict(torch.load(path, weights_only=True, map_location="cpu"), strict=True)
    result["strict_load"] = True
    model.cpu().eval()
    clips, clinical = torch.zeros(1, 1, 1, *dimensions[:2]), torch.zeros(1, dimensions[2])
    with torch.inference_mode():
        logits = model(clips, clinical, torch.ones(1, 1, dtype=torch.bool))
    passed = tuple(logits.shape) == (1, 2) and bool(torch.isfinite(logits).all())
    result["smoke"] = {"passed": passed, "output_shape": list(logits.shape),
                       "clips_shape": list(clips.shape), "clinical_shape": list(clinical.shape)}
    result["parameter_count"] = sum(parameter.numel() for parameter in model.parameters())
    result["checkpoint_usable"] = passed and actual == expected


def audit_checkpoint(directory: Path) -> dict:
    manifest_path, checkpoint = directory / "manifest-fusion.json", directory / "model-fusion.pt"
    result = {"run": directory.name, "manifest_present": manifest_path.is_file(),
              "checkpoint_present": checkpoint.is_file(), "checkpoint_usable": False,
              "integrity": {"status": "unavailable"}, "strict_load": False, "smoke": {"passed": False}}
    stage = "manifest"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        evaluation = manifest.get("evaluation", {})
        result.update({key: manifest.get(key) for key in (
            "architecture", "input_mode", "metadata_dim", "initialization", "pretrained_weights", "calibration_status")})
        result["evaluation_architecture"] = evaluation.get("architecture")
        result["evaluation_gate"] = {key: manifest.get("evaluation_gate", {}).get(key)
                                     for key in ("status", "external_validation")}
        metrics = evaluation.get("pooled_metrics", {})
        result["historical_pooled_metrics"] = {key: metrics[key] for key in METRICS if key in metrics
            and (metrics[key] is None or type(metrics[key]) in (int, float) and math.isfinite(metrics[key]))}
        result["subjects"] = subject_summary(evaluation)
        stage = "checkpoint"
        if manifest["artifact_path"] != checkpoint.name:
            raise ValueError("manifest must reference its local model-fusion.pt")
        check_checkpoint(checkpoint, manifest, result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, EOFError, UnpicklingError) as error:
        # Exception messages can contain subject IDs or checkpoint dictionary keys.
        result["error"] = {"stage": stage, "type": type(error).__name__}
    return result


def audit_root(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("audit root must be an existing directory")
    directories = {path.parent for name in ("manifest-fusion.json", "model-fusion.pt")
                   for path in root.glob(f"output*/{name}") if path.is_file()}
    runs = [audit_checkpoint(directory) for directory in sorted(directories)]
    legacy = Path(__file__).resolve().parents[1] / "training-output-residual/model-audio-residual.pt"
    return {"model_file_count": sum(run["checkpoint_present"] for run in runs), "runs": runs,
            "legacy_v2": {"source": "deploy/model-space/README.md", "evidence": "documentation_only",
                          "referenced_checkpoint": "training-output-residual/model-audio-residual.pt",
                          "checkpoint_present": legacy.is_file(), "measured": False},
            "notes": ["Metrics are historical manifest claims, not recomputed or tied to weights by this audit.",
                      "sample_count counts pooled test entries, not necessarily unique subjects. Repeats alone do not invalidate AUROC.",
                      "Checkpoint usability means integrity + strict load + finite smoke only, not deployment approval."]}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; refusing to overwrite")
    report = audit_root(args.root)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Audited {len(report['runs'])} runs / {report['model_file_count']} checkpoints; "
          f"{sum(run['checkpoint_usable'] for run in report['runs'])} checkpoint-usable.")


if __name__ == "__main__":
    main()
