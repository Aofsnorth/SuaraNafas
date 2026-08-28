from __future__ import annotations

from src.runtime_config import load_configured_model


def test_missing_manifest_keeps_backend_degraded(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_MANIFEST_PATH", raising=False)

    model = load_configured_model()

    assert model.is_available is False
