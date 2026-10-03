"""Run the auditable frozen-AST and CNN benchmark on the local CODA subset."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.model_selection import StratifiedKFold

from training.ast_features import ASTConfig, extract_patient_embeddings
from training.ast_head import benchmark_heads
from training.cnn_benchmark import benchmark_cnns
from training.dataset import PatientExample, load_patient_examples


DEFAULT_SEED = 42
DEFAULT_MAX_CLIPS = 8
DEFAULT_FOLDS = 3


def _partitions(examples: list[PatientExample], folds: int, seed: int) -> list[dict[str, Any]]:
    labels = np.asarray([example.label for example in examples])
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    partitions = []
    all_indices = np.arange(len(examples))
    for fold, (train_and_validation, test) in enumerate(splitter.split(all_indices, labels)):
        inner = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed + fold)
        train_relative, validation_relative = next(
            inner.split(train_and_validation, labels[train_and_validation])
        )
        partitions.append({
            "fold": fold,
            "train": train_and_validation[train_relative].tolist(),
            "validation": train_and_validation[validation_relative].tolist(),
            "test": test.tolist(),
        })
    return partitions


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def _load_examples(args: argparse.Namespace) -> list[PatientExample]:
    return load_patient_examples(
        args.clinical_metadata,
        args.additional_metadata,
        args.solicited_metadata,
        args.audio_root,
        max_clips=args.max_clips_per_subject,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    existing = [output / name for name in ("cnn-reports.json", "head-reports.json")]
    if any(path.exists() for path in existing):
        raise ValueError("benchmark output already contains reports; choose a new output directory")
    examples = _load_examples(args)
    partitions = _partitions(examples, args.folds, args.seed)
    _write_json(output / "partitions.json", partitions)
    _write_json(output / "cohort.json", {
        "subjects": len(examples),
        "positive": sum(example.label for example in examples),
        "negative": sum(1 - example.label for example in examples),
        "selected_clips": sum(len(example.audio_paths) for example in examples),
        "max_clips_per_subject": args.max_clips_per_subject,
        "seed": args.seed,
    })

    print("=== Frozen AST embeddings ===", flush=True)
    config = ASTConfig(batch_size=args.ast_batch_size, device=args.device)
    embeddings = extract_patient_embeddings(examples, output, config)
    np.save(output / "patient_embeddings.npy", embeddings, allow_pickle=False)
    _write_json(output / "ast_provenance.json", {
        "model_id": config.model_id, "revision": config.revision,
        "device": args.device, "embedding_shape": list(embeddings.shape),
    })

    print("=== CNN comparison: fresh v3 and v4 ===", flush=True)
    cnn_reports = benchmark_cnns(
        examples, partitions, output / "cnn", epochs=args.cnn_epochs,
        batch_size=args.cnn_batch_size, seed=args.seed, device=args.device,
    )
    _write_json(output / "cnn-reports.json", cnn_reports)

    print("=== AST head comparison: audio / clinical / fusion ===", flush=True)
    head_reports = benchmark_heads(
        examples, embeddings, partitions, output / "heads", epochs=args.head_epochs,
        seed=args.seed, device=args.device,
    )
    _write_json(output / "head-reports.json", head_reports)
    return {"cnn": cnn_reports, "heads": head_reports}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinical-metadata", type=Path, required=True)
    parser.add_argument("--additional-metadata", type=Path, required=True)
    parser.add_argument("--solicited-metadata", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--folds", type=int, default=DEFAULT_FOLDS)
    parser.add_argument("--max-clips-per-subject", type=int, default=DEFAULT_MAX_CLIPS)
    parser.add_argument("--ast-batch-size", type=int, default=1)
    parser.add_argument("--cnn-batch-size", type=int, default=16)
    parser.add_argument("--cnn-epochs", type=int, default=8)
    parser.add_argument("--head-epochs", type=int, default=120)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but unavailable; use --device cpu explicitly")
    if args.folds < 2 or args.max_clips_per_subject < 1:
        raise SystemExit("folds must be >= 2 and max clips must be positive")
    run(args)


if __name__ == "__main__":
    main()
