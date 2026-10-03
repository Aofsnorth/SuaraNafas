from __future__ import annotations

import csv
from pathlib import Path

import pytest

from training.dataset import _spread_sample, DatasetError, load_patient_examples
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


def test_dataset_loader_skips_a_participant_without_a_reference_standard(tmp_path) -> None:
    """CODA_TB_0229 has a blank microbiological result. One unlabelled row must
    not abort the other thousand participants, and must not be dropped
    silently either."""
    paths = build_metadata_files(tmp_path, clinical_label="1", microbiology_label="")

    with pytest.raises(DatasetError, match="no patients"):
        load_patient_examples(*paths[:3], paths[3], max_clips=8)


def test_dataset_loader_keeps_labelled_participants_when_one_is_unlabelled(tmp_path) -> None:
    """The real dataset combines both cases in one file set."""
    clinical = tmp_path / "clinical.csv"
    additional = tmp_path / "additional.csv"
    solicited = tmp_path / "solicited.csv"
    audio = tmp_path / "audio"
    audio.mkdir()

    rows_clinical = ["participant,sex,age,height,weight,reported_cough_dur"]
    rows_additional = ["participant,Microbiologicreferencestandard"]
    rows_solicited = ["participant,filename"]
    for index, reference in enumerate(["Positive", "Negative", ""]):
        identifier = f"P{index}"
        rows_clinical.append(f"{identifier},Male,40,170,60,30")
        rows_additional.append(f"{identifier},{reference}")
        clip = audio / f"{identifier}.wav"
        clip.write_bytes(b"RIFF" + b"\x00" * 40)
        rows_solicited.append(f"{identifier},{clip.name}")

    clinical.write_text("\n".join(rows_clinical), encoding="utf-8")
    additional.write_text("\n".join(rows_additional), encoding="utf-8")
    solicited.write_text("\n".join(rows_solicited), encoding="utf-8")

    examples = load_patient_examples(clinical, additional, solicited, audio, max_clips=8)

    assert [example.patient_id for example in examples] == ["P0", "P1"]
    assert [example.label for example in examples] == [1, 0]


def test_dataset_loader_treats_na_as_a_missing_measurement(tmp_path) -> None:
    """CODA writes "NA" rather than an empty cell for a missing height."""
    clinical = tmp_path / "clinical.csv"
    additional = tmp_path / "additional.csv"
    solicited = tmp_path / "solicited.csv"
    audio = tmp_path / "audio"
    audio.mkdir()
    clinical.write_text(
        "participant,sex,age,height,weight,reported_cough_dur\nP0,Male,40,NA,60,30\n",
        encoding="utf-8",
    )
    additional.write_text(
        "participant,Microbiologicreferencestandard,HIVstatus\nP0,Positive,\n", encoding="utf-8"
    )
    clip = audio / "P0.wav"
    clip.write_bytes(b"RIFF" + b"\x00" * 40)
    solicited.write_text(f"participant,filename\nP0,{clip.name}\n", encoding="utf-8")

    examples = load_patient_examples(clinical, additional, solicited, audio, max_clips=8)

    assert len(examples) == 1
    assert examples[0].metadata["height"] == ""
    # A blank HIV result is "unknown", not an error and not "negative".
    assert examples[0].metadata["HIVstatus"] == "Unknown"


def test_dataset_loader_rejects_a_nonnumeric_height(tmp_path) -> None:
    clinical = tmp_path / "clinical.csv"
    additional = tmp_path / "additional.csv"
    solicited = tmp_path / "solicited.csv"
    audio = tmp_path / "audio"
    audio.mkdir()
    clinical.write_text(
        "participant,sex,age,height,weight,reported_cough_dur\nP0,Male,40,170cm,60,30\n",
        encoding="utf-8",
    )
    additional.write_text(
        "participant,Microbiologicreferencestandard,HIVstatus\nP0,Positive,Negative\n",
        encoding="utf-8",
    )
    clip = audio / "P0.wav"
    clip.write_bytes(b"RIFF" + b"\x00" * 40)
    solicited.write_text(f"participant,filename\nP0,{clip.name}\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="height"):
        load_patient_examples(clinical, additional, solicited, audio, max_clips=8)


class TestSpreadSample:
    def test_short_input_is_returned_whole(self) -> None:
        items = [Path(f"{i}.wav") for i in range(3)]

        assert _spread_sample(items, 8) == items

    def test_long_input_is_capped_at_the_limit(self) -> None:
        items = [Path(f"{i}.wav") for i in range(100)]

        assert len(_spread_sample(items, 8)) == 8

    def test_the_sample_covers_both_ends_of_the_input(self) -> None:
        """Capping from the head would drop the second source entirely."""
        items = [Path(f"{i}.wav") for i in range(100)]

        picked = _spread_sample(items, 4)

        assert picked[0] == items[0]
        assert picked[-1] == items[-1]

    def test_a_zero_limit_returns_nothing(self) -> None:
        assert _spread_sample([Path("a.wav")], 0) == []


class TestLongitudinalClips:
    def _write(self, tmp_path: Path, *, with_longitudinal: bool) -> tuple:
        clinical = tmp_path / "clinical.csv"
        additional = tmp_path / "additional.csv"
        solicited = tmp_path / "solicited.csv"
        audio = tmp_path / "audio"
        audio.mkdir()
        clinical.write_text(
            "participant,sex,age,height,weight,reported_cough_dur\n"
            "P0,Male,40,170,60,30\n",
            encoding="utf-8",
        )
        additional.write_text(
            "participant,Microbiologicreferencestandard,HIVstatus\n"
            "P0,Positive,Negative\n",
            encoding="utf-8",
        )
        rows = ["participant,filename"]
        for index in range(2):
            clip = audio / f"sol-{index}.wav"
            clip.write_bytes(b"RIFF" + b"\x00" * 40)
            rows.append(f"P0,{clip.name}")
        solicited.write_text("\n".join(rows), encoding="utf-8")

        long_meta = tmp_path / "long.csv"
        long_audio = tmp_path / "long_audio"
        long_audio.mkdir()
        long_rows = ["participant,filename,sound_prediction_score"]
        for index in range(3):
            clip = long_audio / f"lon-{index}.wav"
            clip.write_bytes(b"RIFF" + b"\x00" * 40)
            long_rows.append(f"P0,{clip.name},0.9")
        long_meta.write_text("\n".join(long_rows), encoding="utf-8")
        return clinical, additional, solicited, audio, long_meta, long_audio

    def test_without_longitudinal_metadata_only_solicited_clips_are_used(self, tmp_path) -> None:
        paths = self._write(tmp_path, with_longitudinal=True)

        examples = load_patient_examples(
            paths[0], paths[1], paths[2], paths[3], max_clips=8
        )

        assert len(examples[0].audio_paths) == 2

    def test_longitudinal_clips_are_mixed_with_the_solicited_ones(self, tmp_path) -> None:
        paths = self._write(tmp_path, with_longitudinal=True)

        examples = load_patient_examples(
            paths[0],
            paths[1],
            paths[2],
            paths[3],
            max_clips=8,
            longitudinal_metadata=paths[4],
            longitudinal_audio_root=paths[5],
        )

        names = {path.name.split("-")[0] for path in examples[0].audio_paths}
        assert names == {"sol", "lon"}

    def test_the_cap_keeps_clips_from_both_sources(self, tmp_path) -> None:
        """A head-based cap would keep only the solicited clips and waste the
        natural coughs that were just loaded."""
        paths = self._write(tmp_path, with_longitudinal=True)

        examples = load_patient_examples(
            paths[0],
            paths[1],
            paths[2],
            paths[3],
            max_clips=4,
            longitudinal_metadata=paths[4],
            longitudinal_audio_root=paths[5],
        )

        names = {path.name.split("-")[0] for path in examples[0].audio_paths}
        assert len(examples[0].audio_paths) == 4
        assert names == {"sol", "lon"}

    def test_a_longitudinal_root_without_metadata_is_rejected(self, tmp_path) -> None:
        paths = self._write(tmp_path, with_longitudinal=True)

        with pytest.raises(DatasetError, match="longitudinal_audio_root"):
            load_patient_examples(
                paths[0],
                paths[1],
                paths[2],
                paths[3],
                max_clips=8,
                longitudinal_metadata=paths[4],
            )
