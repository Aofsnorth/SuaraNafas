from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from training.dataset import DatasetError, PatientExample

VALID_LABELS = {"NTB": 0, "TB": 1}


def _read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as error:
        raise DatasetError(f"could not read TBscreen metadata: {path}") from error


def _audio_index(audio_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for audio_path in audio_root.rglob("*.wav"):
        key = audio_path.stem.casefold()
        if key in index and index[key] != audio_path:
            raise DatasetError(f"duplicate TBscreen audio stem: {audio_path.stem}")
        index[key] = audio_path
    if not index:
        raise DatasetError(f"no WAV files found under {audio_root}")
    return index


def load_tb_screen_examples(
    metadata_paths: tuple[str | Path, ...],
    audio_root: str | Path,
    *,
    max_clips: int,
) -> list[PatientExample]:
    """Load consented TBscreen coughs and group every clip by subject."""
    if max_clips < 1:
        raise DatasetError("max_clips must be positive")
    if not metadata_paths:
        raise DatasetError("at least one TBscreen metadata file is required")

    audio_by_stem = _audio_index(Path(audio_root))
    clips_by_subject: dict[str, list[Path]] = defaultdict(list)
    labels_by_subject: dict[str, int] = {}

    for metadata_path in metadata_paths:
        for row in _read_rows(Path(metadata_path)):
            subject = str(row.get("subject", "")).strip()
            label_name = str(row.get("Label", "")).strip().upper()
            consent = str(row.get("Permission_sound", "")).strip().casefold()
            audio_stem = Path(str(row.get("path", "")).strip()).stem
            if not subject or label_name not in VALID_LABELS or consent != "yes":
                continue
            label = VALID_LABELS[label_name]
            previous_label = labels_by_subject.setdefault(subject, label)
            if previous_label != label:
                raise DatasetError(f"conflicting labels for subject {subject}")
            audio_path = audio_by_stem.get(audio_stem.casefold())
            if audio_path is not None and audio_path not in clips_by_subject[subject]:
                clips_by_subject[subject].append(audio_path)

    examples = [
        PatientExample(
            patient_id=subject,
            label=labels_by_subject[subject],
            audio_paths=tuple(sorted(paths)[:max_clips]),
            metadata={},
        )
        for subject, paths in sorted(clips_by_subject.items())
        if paths
    ]
    if not examples:
        raise DatasetError("no TBscreen subjects have valid labels and downloaded audio")
    return examples
