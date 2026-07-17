import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
CLINICAL_CSV = ROOT / "CODA_TB_Clinical_Meta_Info.csv"
ADDITIONAL_CSV = ROOT / "CODA_TB_additional_variables_train.csv"
OUTPUT = Path(__file__).resolve().parent / "deployment_config.json"

NUMERIC_FEATURES = [
    "age",
    "height",
    "weight",
    "reported_cough_dur",
    "heart_rate",
    "temperature",
]

BINARY_FEATURES = [
    "tb_prior",
    "tb_prior_Pul",
    "tb_prior_Extrapul",
    "tb_prior_Unknown",
    "hemoptysis",
    "weight_loss",
    "smoke_lweek",
    "fever",
    "night_sweats",
]

CLINICAL_FEATURE_ORDER = [
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
]


def main():
    clinical = pd.read_csv(CLINICAL_CSV)
    additional = pd.read_csv(ADDITIONAL_CSV)
    merged = pd.merge(clinical, additional, on="participant", how="inner")

    numeric_stats = {}
    for field in NUMERIC_FEATURES:
        values = pd.to_numeric(merged[field], errors="coerce")
        numeric_stats[field] = {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "count": int(values.count()),
        }

    config = {
        "schema_version": 1,
        "model": {
            "metadata_dim": 43,
            "num_grid_cells": 16,
            "num_prototypes": 10,
            "weights_file": "tb_cough_edge_weights_fp32.pt",
        },
        "audio": {
            "sample_rate": 16000,
            "duration_seconds": 0.55,
            "n_mels": 128,
            "n_fft": 1024,
            "hop_length": 256,
            "target_frames": 36,
            "maximum_clips": 24,
            "recommended_clips": 5,
            "minimum_rms": 1e-5,
        },
        "numeric_features": NUMERIC_FEATURES,
        "binary_features": BINARY_FEATURES,
        "clinical_feature_order": CLINICAL_FEATURE_ORDER,
        "countries": ["IN", "MG", "PH", "SA", "TZ", "UG", "VN"],
        "hiv_statuses": ["Negative", "Positive", "Unknown"],
        "numeric_stats": numeric_stats,
        "thresholds": {
            "screening": 0.2596,
            "balanced": 0.4084,
            "default": 0.5,
            "max_accuracy": 0.6803,
        },
        "disclaimer": (
            "This tool provides preliminary TB risk screening only and is not "
            "a diagnosis. Seek professional assessment and microbiological testing."
        ),
    }

    OUTPUT.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT}")
    print(json.dumps(numeric_stats, indent=2))


if __name__ == "__main__":
    main()
