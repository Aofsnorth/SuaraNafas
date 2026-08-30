from __future__ import annotations

from fastapi.testclient import TestClient

from app import create_app
from src.model_gateway import ScreeningPrediction
from tests.factories import build_metadata_json, build_wav


class ReadyModel:
    @property
    def is_available(self) -> bool:
        return True

    @property
    def supported_countries(self) -> frozenset[str]:
        return frozenset({"PH", "IN", "MG", "SA", "TZ", "UG", "VN"})

    @property
    def deployment_status(self) -> str:
        return "validated"

    def predict(self, audio, qualities, metadata) -> ScreeningPrediction:
        return ScreeningPrediction(
            tb_risk_probability=0.42,
            risk_band="elevated",
            accepted_clips=len(audio),
            quality_status="acceptable",
            uncertainty=0.18,
            model_name="test model",
            model_version="test-0.1",
            calibration_status="not_calibrated",
        )


class CandidateModel(ReadyModel):
    @property
    def deployment_status(self) -> str:
        return "candidate"


def build_client() -> TestClient:
    return TestClient(create_app())


def test_health_reports_untrained_backend() -> None:
    response = build_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "service": "SuaraNafas research screening API",
        "model_status": "unavailable",
        "prediction_enabled": False,
    }


def test_predict_refuses_to_score_without_validated_model() -> None:
    response = build_client().post(
        "/predict",
        data={"metadata": build_metadata_json()},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"


def test_predict_rejects_missing_metadata_before_model_check() -> None:
    response = build_client().post(
        "/predict",
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_METADATA"


def test_predict_rejects_oversized_audio_before_reading_model() -> None:
    response = build_client().post(
        "/predict",
        data={"metadata": build_metadata_json()},
        files={"audio": ("cough.wav", b"x" * (15 * 1024 * 1024 + 1), "audio/wav")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "AUDIO_TOO_LARGE"


def test_predict_rejects_unsupported_content_type() -> None:
    response = build_client().post(
        "/predict",
        data={"metadata": build_metadata_json()},
        files={"audio": ("cough.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "UNSUPPORTED_AUDIO_TYPE"


def test_candidate_model_stays_degraded_and_explicitly_labeled() -> None:
    client = TestClient(create_app(CandidateModel()))

    health_response = client.get("/health")
    prediction_response = client.post(
        "/predict",
        data={"metadata": build_metadata_json(Country="PH")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "degraded"
    assert health_response.json()["model_status"] == "candidate"
    assert health_response.json()["prediction_enabled"] is True
    assert prediction_response.status_code == 200
    assert prediction_response.json()["model_status"] == "candidate"
    assert prediction_response.json()["model"]["status"] == "candidate"


def test_predict_returns_screening_contract_for_ready_model() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="PH")},
        files=[
            ("audio", ("cough-1.wav", build_wav(), "audio/wav")),
            ("audio", ("cough-2.wav", build_wav(frequency_hz=330), "audio/wav")),
        ],
    )

    assert response.status_code == 200
    assert response.json()["tb_risk_probability"] == 0.42
    assert response.json()["accepted_clips"] == 2
    assert response.json()["out_of_distribution"] is False
    assert response.json()["model"]["version"] == "test-0.1"
    assert response.json()["model_name"] == "test model"
    assert response.json()["model_version"] == "test-0.1"
    assert response.json()["model_status"] == "validated"


def test_predict_rejects_more_than_eight_clips() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="PH")},
        files=[
            ("audio", (f"cough-{index}.wav", build_wav(), "audio/wav"))
            for index in range(9)
        ],
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TOO_MANY_AUDIO_CLIPS"


def test_predict_does_not_score_country_outside_training_distribution() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="ID")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "OUT_OF_DISTRIBUTION"
