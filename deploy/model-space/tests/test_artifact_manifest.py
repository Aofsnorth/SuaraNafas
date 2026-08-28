from __future__ import annotations

import json

import pytest

from training.artifact_manifest import (
    ArtifactManifestError,
    load_artifact_manifest,
    verify_artifact_digest,
)


def test_rejects_manifest_without_required_evaluation_gate(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "model_name": "example",
                "model_version": "0.1.0",
                "artifact_path": "model.pt",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactManifestError, match="evaluation"):
        load_artifact_manifest(manifest_path)


def test_rejects_checksum_mismatch(tmp_path) -> None:
    artifact_path = tmp_path / "model.pt"
    artifact_path.write_bytes(b"model")

    with pytest.raises(ArtifactManifestError, match="checksum"):
        verify_artifact_digest(artifact_path, "b" * 64)


def test_accepts_manifest_only_when_gate_is_explicitly_passed(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "model_name": "example",
                "model_version": "0.1.0",
                "artifact_path": "model.pt",
                "artifact_sha256": "a" * 64,
                "training_dataset": "CODA-TB",
                "split_strategy": "patient_grouped",
                "evaluation_gate": {"status": "passed", "external_validation": True},
            }
        ),
        encoding="utf-8",
    )

    manifest = load_artifact_manifest(manifest_path)

    assert manifest.model_name == "example"
    assert manifest.evaluation_status == "passed"
    assert manifest.thresholds == {"elevated": 0.35, "higher": 0.65}
