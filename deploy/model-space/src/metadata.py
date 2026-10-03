from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


# CODA TB DREAM collected solicited coughs in exactly these seven countries.
# Internally these are stored as ISO 3166-1 alpha-2 codes.
CODA_TB_COUNTRIES = frozenset({"IN", "MG", "PH", "ZA", "TZ", "UG", "VN"})

# The CODA metadata files do NOT use ISO codes. Verified against
# CODA_TB_additional_variables_train.csv: the Country column contains
# UG, PH, VN, MG, SA, IN, TZ and never ZA. "SA" there is South Africa, not
# Saudi Arabia, which is not a CODA site.
#
# Renaming the constant to ZA without mapping at load time did not fix the
# bug it was meant to fix: it silently rejected all 137 South African
# participants (12.4% of the cohort) as out-of-distribution. The dataset code
# has to be translated on the way in, and the internal code has to stay ISO so
# the API and the manifest mean the same thing.
CODA_TB_COUNTRY_ALIASES = {"SA": "ZA"}

# TBscreen was collected at KEMRI, Nairobi, Kenya and is the only cohort this
# repository currently trains on. Kenya is not a CODA site, so it is listed
# separately instead of being smuggled into the CODA set.
TBSCREEN_COUNTRIES = frozenset({"KE"})

SUPPORTED_CODA_COUNTRIES = CODA_TB_COUNTRIES | TBSCREEN_COUNTRIES

# Indonesia is deliberately absent. No Indonesian TB cough cohort is part of
# any dataset this project may train on, so accepting "ID" would assert a
# validity that has never been measured. See docs/DATASET_PROTOCOL.md.
UNVALIDATED_COUNTRIES = frozenset({"ID"})

YES_NO_VALUES = frozenset({"Yes", "No"})
HIV_VALUES = frozenset({"Negative", "Positive", "Unknown"})
SEX_VALUES = frozenset({"Male", "Female"})


class MetadataValidationError(ValueError):
    """Raised when clinical metadata violates the inference contract."""


@dataclass(frozen=True)
class ClinicalMetadata:
    sex: str
    age: float
    height: float
    weight: float
    reported_cough_dur: float
    tb_prior: str
    tb_prior_pulmonary: str
    tb_prior_extrapulmonary: str
    tb_prior_unknown: str
    hemoptysis: str
    weight_loss: str
    smoked_last_week: str
    fever: str
    night_sweats: str
    hiv_status: str
    country: str
    heart_rate: float | None
    temperature: float | None

    @property
    def is_country_out_of_distribution(self) -> bool:
        return self.country not in SUPPORTED_CODA_COUNTRIES


def _require_choice(
    payload: Mapping[str, Any],
    field: str,
    allowed: frozenset[str],
) -> str:
    value = payload.get(field)
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise MetadataValidationError(f'{field} must be one of: {choices}')
    return str(value)


def _number(
    payload: Mapping[str, Any],
    field: str,
    minimum: float,
    maximum: float,
    *,
    optional: bool = False,
) -> float | None:
    value = payload.get(field)
    if optional and value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetadataValidationError(f"{field} must be numeric")
    number = float(value)
    if not minimum <= number <= maximum:
        raise MetadataValidationError(
            f"{field} must be between {minimum:g} and {maximum:g}"
        )
    return number


def _validate_prior_tb_consistency(payload: Mapping[str, Any], tb_prior: str) -> None:
    prior_fields = ("tb_prior_Pul", "tb_prior_Extrapul", "tb_prior_Unknown")
    prior_values = [_require_choice(payload, field, YES_NO_VALUES) for field in prior_fields]
    yes_count = prior_values.count("Yes")
    if tb_prior == "No" and yes_count != 0:
        raise MetadataValidationError(
            "tb_prior_Pul, tb_prior_Extrapul, and tb_prior_Unknown must be No when tb_prior is No"
        )
    if tb_prior == "Yes" and yes_count != 1:
        raise MetadataValidationError(
            "exactly one prior TB location must be Yes when tb_prior is Yes"
        )


def normalise_country(value: Any) -> str:
    """Translate a dataset country code to the internal ISO 3166-1 alpha-2 code.

    CODA's own metadata spells South Africa "SA". The API and the manifest
    use "ZA". Both paths have to agree, or 12% of the cohort disappears at the
    gate without anyone noticing.
    """
    code = str(value or "").strip().upper()
    return CODA_TB_COUNTRY_ALIASES.get(code, code)


def validate_metadata(payload: Mapping[str, Any]) -> ClinicalMetadata:
    """Validate metadata supplied by the Next.js screening proxy."""
    tb_prior = _require_choice(payload, "tb_prior", YES_NO_VALUES)
    _validate_prior_tb_consistency(payload, tb_prior)

    country = normalise_country(payload.get("Country"))
    if len(country) != 2:
        raise MetadataValidationError("Country must be a two-letter code")

    return ClinicalMetadata(
        sex=_require_choice(payload, "sex", SEX_VALUES),
        age=_required_number(payload, "age", 1, 120),
        height=_required_number(payload, "height", 50, 260),
        weight=_required_number(payload, "weight", 10, 350),
        reported_cough_dur=_required_number(payload, "reported_cough_dur", 0, 3650),
        tb_prior=tb_prior,
        tb_prior_pulmonary=str(payload["tb_prior_Pul"]),
        tb_prior_extrapulmonary=str(payload["tb_prior_Extrapul"]),
        tb_prior_unknown=str(payload["tb_prior_Unknown"]),
        hemoptysis=_require_choice(payload, "hemoptysis", YES_NO_VALUES),
        weight_loss=_require_choice(payload, "weight_loss", YES_NO_VALUES),
        smoked_last_week=_require_choice(payload, "smoke_lweek", YES_NO_VALUES),
        fever=_require_choice(payload, "fever", YES_NO_VALUES),
        night_sweats=_require_choice(payload, "night_sweats", YES_NO_VALUES),
        hiv_status=_require_choice(payload, "HIVstatus", HIV_VALUES),
        country=country.strip().upper(),
        heart_rate=_number(payload, "heart_rate", 25, 250, optional=True),
        temperature=_number(payload, "temperature", 30, 45, optional=True),
    )


def encode_clinical_metadata(
    metadata: ClinicalMetadata,
    preprocessing: Mapping[str, Any],
    *,
    cough_count: int,
) -> list[float]:
    """Encode validated clinical data in the exact training-column order."""
    feature_order = preprocessing["clinical_feature_order"]
    numeric_stats = preprocessing["numeric_stats"]
    encoded = {feature: 0.0 for feature in feature_order}
    encoded["sex"] = 1.0 if metadata.sex == "Male" else 0.0

    numeric_values = {
        "age": metadata.age,
        "height": metadata.height,
        "weight": metadata.weight,
        "reported_cough_dur": metadata.reported_cough_dur,
        "heart_rate": metadata.heart_rate,
        "temperature": metadata.temperature,
    }
    for field, value in numeric_values.items():
        stats = numeric_stats[field]
        numeric_value = float(stats["mean"] if value is None else value)
        encoded[field] = (numeric_value - float(stats["mean"])) / (
            float(stats["std"]) + 1e-8
        )

    binary_values = {
        "tb_prior": metadata.tb_prior,
        "tb_prior_Pul": metadata.tb_prior_pulmonary,
        "tb_prior_Extrapul": metadata.tb_prior_extrapulmonary,
        "tb_prior_Unknown": metadata.tb_prior_unknown,
        "hemoptysis": metadata.hemoptysis,
        "weight_loss": metadata.weight_loss,
        "smoke_lweek": metadata.smoked_last_week,
        "fever": metadata.fever,
        "night_sweats": metadata.night_sweats,
    }
    for field, value in binary_values.items():
        encoded[field] = 1.0 if value == "Yes" else 0.0

    encoded["Numberofcoughsoundscollected"] = float(cough_count)
    country_feature = f"country_{metadata.country}"
    if country_feature in encoded:
        encoded[country_feature] = 1.0
    hiv_feature = {
        "Negative": "hiv_Negative",
        "Positive": "hiv_Positive",
        "Unknown": "hiv_Unknown",
    }[metadata.hiv_status]
    encoded[hiv_feature] = 1.0
    return np.asarray(
        [float(encoded[field]) for field in feature_order],
        dtype=np.float32,
    )


def _required_number(
    payload: Mapping[str, Any],
    field: str,
    minimum: float,
    maximum: float,
) -> float:
    value = _number(payload, field, minimum, maximum)
    if value is None:
        raise MetadataValidationError(f"{field} is required")
    return value
