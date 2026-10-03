import hashlib
import json

import pytest
import torch
from src.model import SPECTROGRAM_CLINICAL_BASELINE_V1, build_screening_model
from training import audit_checkpoints as audit


def write_run(root):
    directory = root / "output-test"
    directory.mkdir()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        model = build_screening_model(SPECTROGRAM_CLINICAL_BASELINE_V1, metadata_dim=3,
            input_mode="fusion", expected_n_mels=8, expected_target_frames=12)
    checkpoint = directory / "model-fusion.pt"
    torch.save(model.state_dict(), checkpoint)
    manifest = {"architecture": SPECTROGRAM_CLINICAL_BASELINE_V1, "metadata_dim": 3,
        "input_mode": "fusion", "artifact_path": checkpoint.name,
        "artifact_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "preprocessing": {"audio": {"n_mels": 8, "target_frames": 12}},
        "calibration_status": "not_calibrated", "evaluation_gate": {"status": "blocked"},
        "evaluation": {"pooled_metrics": {"auroc": 0.75, "sample_count": 2},
            "patient_ids": ["private-test", "private-test"], "labels": [1, 1],
            "folds": [{"train_patient_ids": ["private-train"],
                       "validation_patient_ids": ["private-validation"],
                       "test_patient_ids": ["private-test"]}] * 2}}
    path = directory / "manifest-fusion.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return directory, path, checkpoint


@pytest.mark.parametrize("fault", [None, "hash", "strict", "nonfinite"])
def test_checkpoint_integrity_and_safe_smoke(tmp_path, monkeypatch, fault):
    directory, path, checkpoint = write_run(tmp_path)
    payload = json.loads(path.read_text())
    if fault in ("strict", "nonfinite"):
        state = torch.load(checkpoint, weights_only=True)
        if fault == "strict":
            state.pop(next(iter(state)))
        else:
            state["classifier.2.bias"].fill_(float("nan"))
        torch.save(state, checkpoint)
    if fault:
        payload["artifact_sha256"] = "0" * 64 if fault == "hash" else hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        path.write_text(json.dumps(payload))
    before = path.read_bytes()
    original_load = torch.load
    def safe_load(*args, **kwargs):
        assert kwargs == {"weights_only": True, "map_location": "cpu"}
        return original_load(*args, **kwargs)
    def check_inputs(module, inputs):
        clips, clinical, mask = inputs
        assert not module.training and torch.is_inference_mode_enabled()
        assert clips.device.type == clinical.device.type == mask.device.type == "cpu"
        assert not clips.any() and not clinical.any() and mask.all() and mask.dtype == torch.bool
    monkeypatch.setattr(audit.torch, "load", safe_load)
    with torch.nn.modules.module.register_module_forward_pre_hook(
        lambda module, inputs: check_inputs(module, inputs) if len(inputs) == 3 else None
    ):
        result = audit.audit_checkpoint(directory)
    assert result["checkpoint_usable"] is (fault is None)
    assert (result["strict_load"], result["smoke"]["passed"]) == (fault != "strict", fault in (None, "hash"))
    assert result["integrity"]["status"] == ("mismatch" if fault == "hash" else "verified")
    if fault != "strict":
        assert [result["smoke"][key] for key in ("output_shape", "clips_shape", "clinical_shape")] == [
            [1, 2], [1, 1, 1, 8, 12], [1, 3]]
    assert path.read_bytes() == before


@pytest.mark.parametrize("overlap", [False, True])
def test_cli_reports_counts_without_patient_data(tmp_path, capsys, overlap):
    _, path, _ = write_run(tmp_path)
    payload = json.loads(path.read_text())
    if overlap:
        payload["evaluation"]["folds"][0]["train_patient_ids"].append("private-test")
        path.write_text(json.dumps(payload))
    output = tmp_path / "audit.json"
    audit.main(["--root", str(tmp_path), "--output", str(output)])
    report = json.loads(output.read_text())
    run = report["runs"][0]
    assert report["model_file_count"] == 1 and report["legacy_v2"]["measured"] is False
    assert run["historical_pooled_metrics"] == {"auroc": 0.75, "sample_count": 2}
    assert (run["evaluation_gate"]["status"], run["calibration_status"]) == ("blocked", "not_calibrated")
    subjects = run["subjects"]
    assert subjects["pooled_entries"] == 2 and subjects["pooled_unique_subjects"] == 1
    assert subjects["repeated_test_entries"] == subjects["repeated_test_subjects"] == 1
    assert subjects["fold_union_subjects"] == {"train": 1 + overlap, "validation": 1, "test": 1}
    assert subjects["sample_count_is_not_unique"] is True
    assert [fold["train_test"] for fold in subjects["within_fold_overlap"]] == [int(overlap), 0]
    assert "private-" not in output.read_text() + capsys.readouterr().out
    assert "patient_ids" not in output.read_text() and '"labels"' not in output.read_text()
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        audit.main(["--root", str(tmp_path), "--output", str(output)])
    assert output.read_bytes() == before
