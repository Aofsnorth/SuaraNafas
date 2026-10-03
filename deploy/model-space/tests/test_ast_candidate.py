"""Synthetic snapshots only: no encoder download, CUDA work, or dataset training."""
import json
import sys
from unittest.mock import Mock

import numpy as np
import pytest
import torch

from tests.factories.metadata import build_metadata, build_wav
from training import ast_candidate as candidate
from training.dataset import PatientExample


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    model_dir = candidate.ast.local_model_dir(tmp_path, candidate.ast.ASTConfig())
    model_dir.mkdir(parents=True)
    for name in candidate.ast.SNAPSHOT_FILES:
        (model_dir / name).write_bytes(b"synthetic snapshot")
    (model_dir / "ast_provenance.json").write_text(json.dumps({"model_id": candidate.ast.ASTConfig().model_id,
        "revision": candidate.ast.ASTConfig().revision, "preprocessing_id": candidate.ast.PREPROCESSING_ID,
        "sha256": candidate.ast._snapshot_hashes(model_dir)}))
    metadata = build_metadata(Country="SA")
    path = tmp_path / "clip.wav"
    path.write_bytes(build_wav())
    examples = [PatientExample(f"PRIVATE-{i}", i % 2, (path,), {**metadata, "age": 20 + i}) for i in range(4)]
    report = {"ast_clinical": {"folds": [{"selected_epoch": e, "selected_l2": l, "threshold": t}
        for e, l, t in [(1, .1, .2), (3, .01, .4), (2, .001, .9)]], "oof": {"labels": ["PRIVATE"]},
        "pooled_metrics": {"auroc": .75, "private_ids": ["PRIVATE"]}}, "ast_audio": {"auroc": 1.0}}
    original_refit = candidate.refit_head
    def refit(x, y, **options):
        assert options == {"epochs": 2, "l2": .01, "seed": 42, "device": "cuda"}
        assert x.shape == (4, 795) and list(y) == [0, 1, 0, 1]
        np.testing.assert_allclose(x[:, 769].mean(), 0, atol=1e-7)
        return original_refit(x, y, **{**options, "device": "cpu"})
    monkeypatch.setattr(candidate, "refit_head", refit)
    encoder = Mock()
    encoder.embed_bytes.return_value = np.stack([np.zeros(768), np.full(768, 2)]).astype(np.float32)
    factory = Mock(return_value=encoder)
    monkeypatch.setattr(candidate.ast, "FrozenASTEncoder", factory)
    manifest = candidate.export_candidate(examples, np.ones((4, 768)), report, tmp_path)
    assert "PRIVATE" not in json.dumps(manifest) and manifest["evaluation"]["final_refit_evaluated"] is False
    return tmp_path / "candidate", manifest, metadata, [path, path], factory


def test_export_weights_only_parity_and_cli(bundle, monkeypatch, capsys):
    directory, manifest, metadata, paths, factory = bundle
    state = torch.load(directory / "head.pt", map_location="cpu", weights_only=True)
    assert state["threshold"] == .4 and state["threshold_status"] == "provisional_validation_median_only"
    assert state["clinical_preprocessor"]["numeric_stats"]["age"]["mean"] == 21.5
    clinical = candidate.encoding.ClinicalPreprocessor.fit([build_metadata(age=20 + i) for i in range(4)])
    expected = candidate.predict_head(state, np.concatenate((np.ones((1, 768)), clinical.transform(metadata, cough_count=2)[None]), axis=1))[0]
    result = candidate.predict_candidate(directory, paths, metadata)
    assert result == {"model_status": "candidate", "research_only": True, "uncalibrated_score": float(expected), "not_for_diagnosis": True}
    factory.assert_called_with(candidate.ast.ASTConfig(batch_size=1, device="cpu"), candidate.ast.local_model_dir(directory.parent, candidate.ast.ASTConfig()))
    metadata_path = directory / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    monkeypatch.setattr(sys, "argv", ["ast_candidate", "--candidate-dir", str(directory), "--audio", *map(str, paths), "--metadata", str(metadata_path)])
    capsys.readouterr()
    candidate.main()
    assert json.loads(capsys.readouterr().out) == result
    assert manifest["evaluation_gate"] == {"status": "blocked", "external_validation": False}


@pytest.mark.parametrize("device", ["cuda", "cuda:0"])
def test_runtime_requests_single_clip_batches_without_changing_provenance(bundle, monkeypatch, device):
    directory, manifest, metadata, paths, factory = bundle
    manifest_bytes = (directory / "manifest.json").read_bytes()
    head = Mock(return_value=np.array([0.25], dtype=np.float32))
    monkeypatch.setattr(candidate, "predict_head", head)
    result = candidate.predict_candidate(directory, paths, metadata, device=device)
    factory.assert_called_with(candidate.ast.ASTConfig(batch_size=1, device=device), candidate.ast.local_model_dir(directory.parent, candidate.ast.ASTConfig()))
    assert head.call_args.kwargs == {"device": device} and result["uncalibrated_score"] == 0.25
    assert (directory / "manifest.json").read_bytes() == manifest_bytes
    assert candidate._snapshot(directory)[1] == manifest["encoder_sha256"]


@pytest.mark.parametrize("change", ["head", "snapshot", "architecture", "artifact_path", "encoder_local_path", "gate", "country", "missing", "category", "numeric", "zero", "nine", "wav", "size"])
def test_rejects_tampering_and_invalid_inputs_before_encoder(bundle, change, monkeypatch):
    directory, manifest, metadata, paths, factory = bundle
    if change in ("architecture", "artifact_path", "encoder_local_path"):
        manifest[change] = "../../outside"
    if change == "gate": manifest["evaluation_gate"]["status"] = "validated"
    if change == "head": (directory / "head.pt").write_bytes(b"tampered")
    if change == "snapshot": (candidate.ast.local_model_dir(directory.parent, candidate.ast.ASTConfig()) / "config.json").write_bytes(b"tampered")
    if change == "country": metadata["Country"] = "ID"
    if change == "missing": metadata.pop("age")
    if change == "category": metadata["sex"] = "invalid"
    if change == "numeric": metadata["age"] = float("inf")
    if change == "zero": paths = []
    if change == "nine": paths *= 5
    if change == "wav": paths[0].write_bytes(b"not WAV")
    if change == "size": monkeypatch.setattr(candidate, "MAX_AUDIO_BYTES", 10)
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError): candidate.predict_candidate(directory, paths, metadata)
    factory.assert_not_called()


@pytest.mark.parametrize("prior", ["Yes", "No", "Not sure"])
@pytest.mark.parametrize("unknown", ["Yes", "No"])
def test_clinical_prior_tb_matches_training_and_preserves_unknown(prior, unknown):
    row = build_metadata(tb_prior=prior, tb_prior_Unknown=unknown)
    original = row.copy()
    preprocessor = candidate.encoding.ClinicalPreprocessor.fit([row])
    actual = candidate._clinical(preprocessor, [row], [2])[0]
    np.testing.assert_array_equal(actual, preprocessor.transform(row, cough_count=2))
    assert actual[preprocessor.feature_order.index("tb_prior")] == float(prior == "Yes")
    assert actual[preprocessor.feature_order.index("tb_prior_Unknown")] == float(unknown == "Yes")
    assert row == original


@pytest.mark.parametrize("field", [f for f in candidate.encoding.BINARY_FIELDS if f != "tb_prior"])
def test_clinical_rejects_not_sure_for_other_binary_fields(field):
    row = build_metadata(**{field: "Not sure"})
    preprocessor = candidate.encoding.ClinicalPreprocessor.fit([row])
    with pytest.raises(ValueError, match="invalid CODA sex or binary category"):
        candidate._clinical(preprocessor, [row], [1])
