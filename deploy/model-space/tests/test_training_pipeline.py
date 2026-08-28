from __future__ import annotations

import json

from training.pipeline import build_candidate_manifest


def test_candidate_manifest_is_blocked_without_external_validation(tmp_path) -> None:
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"candidate")
    preprocessing = {
        "clinical_feature_order": ["age"],
        "numeric_stats": {"age": {"mean": 1.0, "std": 1.0}},
        "countries": ["PH"],
        "audio": {"sample_rate": 16000},
    }

    manifest_path = build_candidate_manifest(
        artifact,
        tmp_path / "manifest.json",
        model_name="test",
        model_version="test-1",
        input_mode="fusion",
        metadata_dim=1,
        supported_countries=["PH"],
        preprocessing=preprocessing,
        evaluation={"test": {"auroc": 0.7}},
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["evaluation_gate"] == {
        "status": "blocked",
        "external_validation": False,
    }
    assert len(payload["artifact_sha256"]) == 64
