"""Research CLI: python -m training.ast_candidate --candidate-dir BENCHMARK/candidate
--audio WAV [WAV ...] --metadata CODA.json [--device cpu]. Raw CODA, NOT web metadata:
all NUMERIC_FIELDS/BINARY_FIELDS, sex, Country, HIVstatus required. Numeric missing
sentinels use fitted means; missing HIV becomes Unknown. API WAV policy: 1-8 clips/15 MiB.
Only tb_prior accepts "Not sure": it encodes as 0, with tb_prior_Unknown unchanged.
Runtime uses batch_size=1 to avoid the observed multi-clip CUDA failure; preprocessing
and provenance are unchanged. Cross-device scores need not be bit-identical.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import torch

from src.audio_validation import validate_wav_audio
from src.metadata import CODA_TB_COUNTRIES
from training import ast_features as ast
from training import encoding
from training.ast_head import ARCHITECTURE, predict_head, refit_head
from training.dataset import _build_payload

POLICY = {"architecture": ARCHITECTURE, "input_mode": "ast_clinical", "input_dim": 795,
          "metadata_dim": 27, "pretrained_weights": True, "model_status": "candidate",
          "research_only": True, "intended_use": "research_only", "calibration_status": "not_calibrated",
          "evaluation_gate": {"status": "blocked", "external_validation": False},
          "encoder_id": ast.ASTConfig().model_id, "encoder_revision": ast.ASTConfig().revision,
          "encoder_local_path": f"../ast_model/{ast.ASTConfig().revision}", "artifact_path": "head.pt",
          "preprocessing_id": ast.PREPROCESSING_ID, "threshold_status": "provisional_validation_median_only"}
MAX_AUDIO_BYTES = 15 * 1024 * 1024
SUMMARY_METRICS = ("auroc", "average_precision", "brier_score", "sensitivity", "specificity", "sample_count")


def _inside(directory, path):
    if path.is_symlink() or not path.resolve().is_relative_to(directory.parent.resolve()):
        raise ValueError("candidate path escapes benchmark root or is a symlink")
    return path


def _snapshot(directory):
    model_dir = ast.local_model_dir(directory.parent.resolve(), ast.ASTConfig())
    paths = {name: _inside(directory, model_dir / name) for name in (*ast.SNAPSHOT_FILES, "ast_provenance.json")}
    ast._verify_snapshot(model_dir, ast.ASTConfig())  # Verify existing files, never download during export/load.
    provenance = json.loads(paths["ast_provenance.json"].read_text(encoding="utf-8"))
    return model_dir, {**provenance["sha256"], "ast_provenance.json": hashlib.sha256(paths["ast_provenance.json"].read_bytes()).hexdigest()}


def _clinical(preprocessor, rows, counts):
    if preprocessor.feature_order != encoding.CLINICAL_FEATURE_ORDER or len(preprocessor.feature_order) != 27:
        raise ValueError("clinical feature order must contain the exact 27 training features")
    stats = np.array([[preprocessor.numeric_stats[f][k] for k in ("mean", "std")] for f in encoding.NUMERIC_FIELDS])
    if set(preprocessor.countries) != CODA_TB_COUNTRIES or not np.isfinite(stats).all() or (stats[:, 1] <= 0).any():
        raise ValueError("invalid clinical preprocessing statistics or countries")
    vectors = []
    for row, count in zip(rows, counts, strict=True):
        required = {*encoding.NUMERIC_FIELDS, *encoding.BINARY_FIELDS, "sex", "Country", "HIVstatus"}
        if not isinstance(row, Mapping) or not required.issubset(row):
            raise ValueError("metadata requires a complete raw CODA row, not web public metadata")
        if row["sex"] not in ("Male", "Female") or any(
            row[field] not in ("Yes", "No") and not (field == "tb_prior" and row[field] == "Not sure")
            for field in encoding.BINARY_FIELDS
        ):
            raise ValueError("invalid CODA sex or binary category")
        if any(isinstance(row[f], bool) for f in encoding.NUMERIC_FIELDS):
            raise ValueError("numeric metadata must not be boolean")
        vectors.append(preprocessor.transform(_build_payload(dict(row), {}), cough_count=count))
    values = np.asarray(vectors, dtype=np.float32)
    if values.shape != (len(rows), 27) or not np.isfinite(values).all():
        raise ValueError("clinical features must be finite with shape (patients, 27)")
    return values


def export_candidate(examples, embeddings, report, output_dir, *, device="cuda", seed=42) -> dict:
    """Refit predeclared ast_clinical; floor an even-fold median epoch. No final-fit evaluation."""
    selected = report["ast_clinical"]
    folds = selected["folds"]
    selections = [[f[k] for k in ("selected_epoch", "selected_l2", "threshold")] for f in folds]
    if not selections or any(type(v) not in (int, float) for row in selections for v in row):
        raise ValueError("fold validation selections must be nonempty and numeric")
    values = np.asarray(selections, dtype=float)
    if (not np.isfinite(values).all() or (values[:, 0] < 1).any()
            or (values[:, 0] != np.floor(values[:, 0])).any() or (values[:, 1] < 0).any()
            or ((values[:, 2] < 0) | (values[:, 2] > 1)).any()):
        raise ValueError("invalid fold validation selections")
    epochs, l2, threshold = np.median(values, axis=0).tolist()
    audio = ast._validate_embeddings(embeddings, len(examples))
    counts = [len(e.audio_paths) for e in examples]
    if not counts or any(not 1 <= count <= 8 for count in counts):
        raise ValueError("each example requires 1-8 selected WAV clips")
    preprocessor = encoding.ClinicalPreprocessor.fit([e.metadata for e in examples])
    features = np.concatenate((audio, _clinical(preprocessor, [e.metadata for e in examples], counts)), axis=1)
    directory = Path(output_dir).resolve() / "candidate"
    _, hashes = _snapshot(directory)
    evaluation = {"scope": "cv_recipe_evidence_not_final_refit_measurement", "final_refit_evaluated": False,
                  "fold_count": len(folds), "pooled_metrics": {k: float(selected["pooled_metrics"][k])
                  for k in SUMMARY_METRICS if k in selected.get("pooled_metrics", {})}}
    json.dumps(evaluation, allow_nan=False)
    directory.mkdir(exist_ok=False)
    state = refit_head(features, [e.label for e in examples], epochs=int(epochs), l2=l2, seed=seed, device=device)
    state.update(clinical_preprocessor=preprocessor.to_dict(), threshold=threshold,
                 threshold_status=POLICY["threshold_status"], input_mode="ast_clinical", seed=int(seed))
    ast._atomic_write(directory / "head.pt", lambda stream: torch.save(state, stream))
    manifest = {**POLICY, "artifact_sha256": hashlib.sha256((directory / "head.pt").read_bytes()).hexdigest(), "encoder_sha256": hashes,
                "evaluation": evaluation, "refit": {"epochs": int(epochs), "l2": l2, "seed": int(seed)}}
    payload = json.dumps(manifest, indent=2, allow_nan=False).encode("utf-8")
    ast._atomic_write(directory / "manifest.json", lambda stream: stream.write(payload))
    return json.loads(payload)


def _clips(paths):
    if not 1 <= len(paths) <= 8:
        raise ValueError("provide 1-8 WAV clips")
    clips, remaining = [], MAX_AUDIO_BYTES
    for path in map(Path, paths):
        if path.suffix.lower() != ".wav":
            raise ValueError("audio must be WAV")
        with path.open("rb") as stream:
            data = stream.read(remaining + 1)
        remaining -= len(data)
        if remaining < 0:
            raise ValueError("total audio exceeds 15 MiB")
        validate_wav_audio(data)
        clips.append(data)
    return clips


def predict_candidate(candidate_dir, audio_paths, metadata, *, device="cpu") -> dict:
    """Explicit blocked-candidate research inference; never thresholds or diagnoses."""
    directory = Path(candidate_dir).absolute()
    manifest = json.loads(_inside(directory, directory / "manifest.json").read_text(encoding="utf-8"))
    if any(manifest.get(k) != v for k, v in POLICY.items()):
        raise ValueError("invalid candidate architecture, paths, identity or research gate")
    model_dir, hashes = _snapshot(directory)
    if manifest.get("encoder_sha256") != hashes:
        raise ValueError("candidate snapshot hash mismatch")
    with _inside(directory, directory / "head.pt").open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest.get("artifact_sha256"):
            raise ValueError("candidate head hash mismatch")
        stream.seek(0)
        state = torch.load(stream, map_location="cpu", weights_only=True)
    if state.get("architecture") != ARCHITECTURE or state.get("input_dim") != 795:
        raise ValueError("invalid candidate head architecture or dimension")
    saved = state["clinical_preprocessor"]
    preprocessor = encoding.ClinicalPreprocessor(tuple(saved["clinical_feature_order"]), saved["numeric_stats"], tuple(saved["countries"]))
    clinical = _clinical(preprocessor, [metadata], [len(audio_paths)])
    clips = _clips(audio_paths)
    with redirect_stdout(sys.stderr):
        encoder = ast.FrozenASTEncoder(ast.ASTConfig(batch_size=1, device=device), model_dir)
        audio = ast._validate_embeddings(encoder.embed_bytes(clips), len(clips)).mean(axis=0, dtype=np.float64).astype(np.float32)
    score = float(predict_head(state, np.concatenate((audio[None, :], clinical), axis=1), device=device)[0])
    return {"model_status": "candidate", "research_only": True, "uncalibrated_score": score, "not_for_diagnosis": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--audio", type=Path, nargs="+", required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    result = predict_candidate(args.candidate_dir, args.audio, json.loads(args.metadata.read_text(encoding="utf-8")), device=args.device)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
