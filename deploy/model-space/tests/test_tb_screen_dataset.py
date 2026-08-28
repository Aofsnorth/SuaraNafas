from __future__ import annotations

import csv

import pytest

from tests.factories import build_wav
from training.dataset import DatasetError
from training.tb_screen_dataset import load_tb_screen_examples


def _write_metadata(path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def _row(subject: str, label: str, stem: str, consent: str = "Yes") -> dict[str, str]:
    return {
        "subject": subject,
        "Label": label,
        "path": stem,
        "Permission_sound": consent,
    }


def test_tb_screen_loader_groups_consented_audio_by_subject(tmp_path) -> None:
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    for stem in ("cough-a", "cough-b", "cough-c"):
        (audio_root / f"{stem}.wav").write_bytes(build_wav())
    metadata = tmp_path / "coughs.csv"
    _write_metadata(
        metadata,
        [
            _row("PID_1", "TB", "cough-a"),
            _row("PID_1", "TB", "cough-b"),
            _row("PID_2", "NTB", "cough-c"),
            _row("PID_3", "TB", "missing", consent="No"),
        ],
    )

    examples = load_tb_screen_examples((metadata,), audio_root, max_clips=8)

    assert [example.patient_id for example in examples] == ["PID_1", "PID_2"]
    assert [example.label for example in examples] == [1, 0]
    assert len(examples[0].audio_paths) == 2
    assert examples[0].metadata == {}


def test_tb_screen_loader_limits_clips_per_subject(tmp_path) -> None:
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    rows = []
    for index in range(3):
        stem = f"cough-{index}"
        (audio_root / f"{stem}.wav").write_bytes(build_wav())
        rows.append(_row("PID_1", "TB", stem))
    metadata = tmp_path / "coughs.csv"
    _write_metadata(metadata, rows)

    examples = load_tb_screen_examples((metadata,), audio_root, max_clips=2)

    assert len(examples[0].audio_paths) == 2


def test_tb_screen_loader_rejects_conflicting_subject_labels(tmp_path) -> None:
    audio_root = tmp_path / "audio"
    audio_root.mkdir()
    (audio_root / "a.wav").write_bytes(build_wav())
    (audio_root / "b.wav").write_bytes(build_wav())
    metadata = tmp_path / "coughs.csv"
    _write_metadata(
        metadata,
        [_row("PID_1", "TB", "a"), _row("PID_1", "NTB", "b")],
    )

    with pytest.raises(DatasetError, match="conflicting labels"):
        load_tb_screen_examples((metadata,), audio_root, max_clips=8)
