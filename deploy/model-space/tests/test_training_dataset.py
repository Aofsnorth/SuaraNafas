from __future__ import annotations

import csv

import pytest

from training.dataset import DatasetError, load_patient_examples
from tests.factories import build_wav


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def build_clinical_row(label: str) -> dict[str, str]:
    return {
        "participant": "p1", "sex": "Male", "age": "30", "height": "170",
        "weight": "60", "reported_cough_dur": "14", "tb_prior": "No",
        "tb_prior_Pul": "No", "tb_prior_Extrapul": "No", "tb_prior_Unknown": "No",
        "hemoptysis": "No", "heart_rate": "80", "temperature": "37",
        "weight_loss": "No", "smoke_lweek": "No", "fever": "Yes",
        "night_sweats": "No", "tb_status": label,
    }


def build_metadata_files(tmp_path, *, clinical_label: str, microbiology_label: str):
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    (audio_root / "a.wav").write_bytes(build_wav())
    (audio_root / "b.wav").write_bytes(build_wav(frequency_hz=330))

    clinical_path = tmp_path / "clinical.csv"
    write_csv(clinical_path, [build_clinical_row(clinical_label)])

    solicited_path = tmp_path / "solicited.csv"
    write_csv(
        solicited_path,
        [
            {"participant": "p1", "filename": "a.wav"},
            {"participant": "p1", "filename": "b.wav"},
        ],
    )

    additional_path = tmp_path / "additional.csv"
    write_csv(
        additional_path,
        [
            {
                "participant": "p1",
                "Country": "PH",
                "HIVstatus": "Unknown",
                "Microbiologicreferencestandard": microbiology_label,
            }
        ],
    )
    return clinical_path, additional_path, solicited_path, audio_root


def test_dataset_loader_groups_audio_by_patient(tmp_path) -> None:
    paths = build_metadata_files(
        tmp_path,
        clinical_label="0",
        microbiology_label="Positive",
    )

    examples = load_patient_examples(*paths[:3], paths[3], max_clips=8)

    assert len(examples) == 1
    assert examples[0].patient_id == "p1"
    assert examples[0].label == 1
    assert len(examples[0].audio_paths) == 2


def test_dataset_loader_uses_microbiological_label_over_clinical_status(tmp_path) -> None:
    paths = build_metadata_files(
        tmp_path,
        clinical_label="1",
        microbiology_label="Negative",
    )

    examples = load_patient_examples(*paths[:3], paths[3], max_clips=8)

    assert examples[0].label == 0


def test_dataset_loader_rejects_missing_microbiological_reference(tmp_path) -> None:
    paths = build_metadata_files(
        tmp_path,
        clinical_label="1",
        microbiology_label="",
    )

    with pytest.raises(DatasetError, match="microbiological"):
        load_patient_examples(*paths[:3], paths[3], max_clips=8)
