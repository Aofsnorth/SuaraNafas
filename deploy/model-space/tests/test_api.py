from __future__ import annotations

import pytest
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
        return frozenset({"PH", "IN", "MG", "ZA", "TZ", "UG", "VN"})

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
    # Indonesia is refused, but with its own code: it is the country this
    # project targets and has no training data for, which is a different
    # statement from "we have never heard of this region".
    assert response.json()["detail"]["code"] == "COUNTRY_NOT_VALIDATED"


def test_predict_reports_unmodelled_country_as_out_of_distribution() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="BR")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "OUT_OF_DISTRIBUTION"


def test_predict_accepts_south_africa_country_code() -> None:
    """ZA is South Africa. The manifest used to declare "SA" (Saudi Arabia),
    so an African participant offered in the UI could never be scored."""
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="ZA")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["tb_risk_probability"] > 0


def test_unvalidated_country_message_is_not_empty() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="ID")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    message = response.json()["detail"]["message"]
    assert "Indonesia" in message


def test_indonesia_is_scored_only_with_explicit_consent() -> None:
    """The consent flag is the only difference between a refusal and a score.

    Indonesia has never appeared in any training cohort, so without this flag the
    request must still be refused rather than silently extrapolated.
    """
    client = TestClient(create_app(ReadyModel()))
    metadata = build_metadata_json(Country="ID")

    refused = client.post(
        "/predict",
        data={"metadata": metadata},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "COUNTRY_NOT_VALIDATED"

    consented = client.post(
        "/predict",
        data={"metadata": metadata, "allow_unvalidated_country": "true"},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert consented.status_code == 200
    body = consented.json()
    assert body["country"] == "ID"
    # The response must carry the limitation forward so the proxy can label it.
    assert body["country_validation_status"] == "unvalidated_experimental"
    assert body["out_of_distribution"] is False


def test_consent_flag_does_not_license_an_unknown_country() -> None:
    """Consent covers Indonesia only; it must not open every country."""
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="BR"), "allow_unvalidated_country": "true"},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "OUT_OF_DISTRIBUTION"


@pytest.mark.parametrize("flag_value", ["1", "yes", "TRUE", ""])
def test_consent_flag_must_be_literal_true(flag_value: str) -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="ID"), "allow_unvalidated_country": flag_value},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "COUNTRY_NOT_VALIDATED"


def test_trained_country_reports_in_distribution_status() -> None:
    response = TestClient(create_app(ReadyModel())).post(
        "/predict",
        data={"metadata": build_metadata_json(Country="PH")},
        files={"audio": ("cough.wav", build_wav(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["country_validation_status"] == "in_training_distribution"
    assert response.json()["country"] == "PH"
