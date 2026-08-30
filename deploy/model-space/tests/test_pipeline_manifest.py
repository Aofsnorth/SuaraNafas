from __future__ import annotations

import json

from training.pipeline import build_candidate_manifest


def test_candidate_manifest_is_blocked_by_default(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"candidate")

    path = build_candidate_manifest(
        artifact,
        tmp_path / "manifest.json",
        model_name="baseline",
        model_version="0.1.0",
        input_mode="fusion",
        metadata_dim=27,
        supported_countries=["PH"],
        preprocessing={"audio": {"sample_rate": 16000}},
        evaluation={"test": {"auroc": 0.75}},
        thresholds={"elevated": 0.2, "higher": 0.55},
        training_dataset="TBscreen",
        architecture="spectrogram_audio_cnn_v1",
        initialization="random_pytorch_default",
        pretrained_weights=False,
        seed=42,
    )

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["evaluation_gate"] == {
        "status": "blocked",
        "external_validation": False,
    }
    assert manifest["training_dataset"] == "TBscreen"
    assert manifest["initialization"] == "random_pytorch_default"
    assert manifest["pretrained_weights"] is False
    assert manifest["training_seed"] == 42
    assert manifest["thresholds"] == {"elevated": 0.2, "higher": 0.55}
    assert manifest["split_strategy"] == "patient_grouped"
    assert manifest["split_stratified"] is True
