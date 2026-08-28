from __future__ import annotations

import pytest

from src.metadata import MetadataValidationError, validate_metadata
from tests.factories import build_metadata


def test_accepts_frontend_metadata_contract() -> None:
    metadata = validate_metadata(build_metadata())

    assert metadata.age == 32
    assert metadata.country == "PH"
    assert metadata.hiv_status == "Unknown"


def test_rejects_missing_required_field() -> None:
    payload = build_metadata()
    payload.pop("fever")

    with pytest.raises(MetadataValidationError, match="fever"):
        validate_metadata(payload)


def test_rejects_inconsistent_prior_tb_fields() -> None:
    with pytest.raises(MetadataValidationError, match="tb_prior_Pul"):
        validate_metadata(build_metadata(tb_prior="No", tb_prior_Pul="Yes"))


def test_marks_indonesia_as_out_of_distribution() -> None:
    metadata = validate_metadata(build_metadata(Country="ID"))

    assert metadata.is_country_out_of_distribution is True


def test_supported_coda_country_is_not_out_of_distribution() -> None:
    metadata = validate_metadata(build_metadata(Country="PH"))

    assert metadata.is_country_out_of_distribution is False
