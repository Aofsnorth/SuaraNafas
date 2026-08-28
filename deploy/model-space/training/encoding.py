from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


CLINICAL_FEATURE_ORDER = (
    "sex",
    "age",
    "height",
    "weight",
    "reported_cough_dur",
    "tb_prior",
    "tb_prior_Pul",
    "tb_prior_Extrapul",
    "tb_prior_Unknown",
    "hemoptysis",
    "heart_rate",
    "temperature",
    "weight_loss",
    "smoke_lweek",
    "fever",
    "night_sweats",
    "Numberofcoughsoundscollected",
    "country_IN",
    "country_MG",
    "country_PH",
    "country_SA",
    "country_TZ",
    "country_UG",
    "country_VN",
    "hiv_Negative",
    "hiv_Positive",
    "hiv_Unknown",
)
NUMERIC_FIELDS = ("age", "height", "weight", "reported_cough_dur", "heart_rate", "temperature")
BINARY_FIELDS = (
    "tb_prior",
    "tb_prior_Pul",
    "tb_prior_Extrapul",
    "tb_prior_Unknown",
    "hemoptysis",
    "weight_loss",
    "smoke_lweek",
    "fever",
    "night_sweats",
)


@dataclass(frozen=True)
class ClinicalPreprocessor:
    feature_order: tuple[str, ...]
    numeric_stats: Mapping[str, Mapping[str, float]]
    countries: tuple[str, ...]

    @classmethod
    def fit(cls, rows: Sequence[Mapping[str, Any]]) -> "ClinicalPreprocessor":
        if not rows:
            raise ValueError("at least one clinical row is required")
        stats: dict[str, dict[str, float]] = {}
        for field in NUMERIC_FIELDS:
            values = [float(row[field]) for row in rows if row.get(field) not in (None, "")]
            if not values:
                raise ValueError(f"numeric field {field} has no usable values")
            mean = float(np.mean(values))
            std = float(np.std(values, ddof=0))
            stats[field] = {"mean": mean, "std": std if std > 1e-8 else 1.0}
        return cls(CLINICAL_FEATURE_ORDER, stats, ("IN", "MG", "PH", "SA", "TZ", "UG", "VN"))

    def transform(self, row: Mapping[str, Any], *, cough_count: int) -> np.ndarray:
        encoded = {field: 0.0 for field in self.feature_order}
        encoded["sex"] = 1.0 if row.get("sex") == "Male" else 0.0
        for field in NUMERIC_FIELDS:
            raw = row.get(field)
            value = float(self.numeric_stats[field]["mean"] if raw in (None, "") else raw)
            stats = self.numeric_stats[field]
            encoded[field] = (value - stats["mean"]) / (stats["std"] + 1e-8)
        for field in BINARY_FIELDS:
            encoded[field] = 1.0 if row.get(field) == "Yes" else 0.0
        encoded["Numberofcoughsoundscollected"] = float(cough_count)
        country = str(row.get("Country", "")).strip().upper()
        if f"country_{country}" in encoded:
            encoded[f"country_{country}"] = 1.0
        hiv = str(row.get("HIVstatus", "Unknown")).strip().title()
        hiv_feature = {"Negative": "hiv_Negative", "Positive": "hiv_Positive", "Unknown": "hiv_Unknown"}.get(hiv)
        if hiv_feature is None:
            raise ValueError("HIVstatus must be Negative, Positive, or Unknown")
        encoded[hiv_feature] = 1.0
        return np.asarray([encoded[field] for field in self.feature_order], dtype=np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clinical_feature_order": list(self.feature_order),
            "numeric_stats": {field: dict(stats) for field, stats in self.numeric_stats.items()},
            "countries": list(self.countries),
        }
