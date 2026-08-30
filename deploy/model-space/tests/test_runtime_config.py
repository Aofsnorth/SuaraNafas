from __future__ import annotations

from pathlib import Path

import pytest

from src.model_gateway import UnavailableScreeningModel
from src.runtime_config import load_configured_model


def test_missing_manifest_keeps_backend_degraded(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("ALLOW_BLOCKED_CANDIDATE", raising=False)
    monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)

    model = load_configured_model()

    assert model.is_available is False
    assert model.deployment_status == "unavailable"


@pytest.mark.parametrize(
    ("environment_value", "expected"),
    [
        ("", False),
        ("false", False),
        ("1", False),
        ("yes", False),
        (" TRUE ", True),
    ],
)
def test_candidate_mode_only_accepts_literal_true(
    monkeypatch,
    environment_value: str,
    expected: bool,
) -> None:
    captured: dict[str, object] = {}
    unavailable_model = UnavailableScreeningModel()

    def fake_loader(
        manifest_path: Path,
        *,
        device: str,
        allow_blocked_candidate: bool,
    ) -> UnavailableScreeningModel:
        captured.update(
            manifest_path=manifest_path,
            device=device,
            allow_blocked_candidate=allow_blocked_candidate,
        )
        return unavailable_model

    monkeypatch.setenv("MODEL_MANIFEST_PATH", "candidate-manifest.json")
    monkeypatch.setenv("ALLOW_BLOCKED_CANDIDATE", environment_value)
    monkeypatch.setenv("DEPLOYMENT_ENV", "development")
    monkeypatch.setattr("src.runtime_config.load_torch_screening_model", fake_loader)

    model = load_configured_model()

    assert model is unavailable_model
    assert captured == {
        "manifest_path": Path("candidate-manifest.json"),
        "device": "cpu",
        "allow_blocked_candidate": expected,
    }


@pytest.mark.parametrize("deployment_environment", [None, "", "production", "prod", "stagin"])
def test_unknown_or_production_environment_never_enables_blocked_candidate(
    monkeypatch,
    deployment_environment: str | None,
) -> None:
    captured: dict[str, object] = {}
    unavailable_model = UnavailableScreeningModel()

    def fake_loader(
        manifest_path: Path,
        *,
        device: str,
        allow_blocked_candidate: bool,
    ) -> UnavailableScreeningModel:
        captured["allow_blocked_candidate"] = allow_blocked_candidate
        return unavailable_model

    monkeypatch.setenv("MODEL_MANIFEST_PATH", "candidate-manifest.json")
    monkeypatch.setenv("ALLOW_BLOCKED_CANDIDATE", "true")
    if deployment_environment is None:
        monkeypatch.delenv("DEPLOYMENT_ENV", raising=False)
    else:
        monkeypatch.setenv("DEPLOYMENT_ENV", deployment_environment)
    monkeypatch.setattr("src.runtime_config.load_torch_screening_model", fake_loader)

    load_configured_model()

    assert captured["allow_blocked_candidate"] is False
