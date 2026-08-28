from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DatasetError(ValueError):
    """Raised when CODA-TB metadata cannot be joined safely."""


@dataclass(frozen=True)
class PatientExample:
    patient_id: str
    label: int
    audio_paths: tuple[Path, ...]
    metadata: dict[str, Any]


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error) as error:
        raise DatasetError(f"could not read metadata file: {path}") from error


def _parse_reference_label(value: str | None) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"positive", "1", "1.0", "yes", "tb", "tb+"}:
        return 1
    if normalized in {"negative", "0", "0.0", "no", "non-tb", "tb-"}:
        return 0
    raise DatasetError(
        "microbiological reference label is missing or unsupported: "
        f"{value!r}"
    )


def _numeric_fields() -> frozenset[str]:
    return frozenset(
        {"age", "height", "weight", "reported_cough_dur", "heart_rate", "temperature"}
    )


def _build_payload(clinical: dict[str, str], additional: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {**clinical, **additional}
    for field in _numeric_fields():
        raw = payload.get(field, "")
        if raw in (None, ""):
            continue
        try:
            payload[field] = float(raw)
        except (TypeError, ValueError) as error:
            raise DatasetError(f"field {field} is not numeric") from error
    return payload


def _audio_index(audio_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in audio_root.rglob("*.wav"):
        key = path.name.casefold()
        if key in index and index[key] != path:
            raise DatasetError(f"duplicate audio basename: {path.name}")
        index[key] = path
    if not index:
        raise DatasetError(f"no WAV files found under {audio_root}")
    return index


def load_patient_examples(
    clinical_path: str | Path,
    additional_path: str | Path,
    solicited_path: str | Path,
    audio_root: str | Path,
    *,
    max_clips: int,
) -> list[PatientExample]:
    """Join CODA metadata and audio while keeping all clips grouped by patient."""
    if max_clips < 1:
        raise DatasetError("max_clips must be positive")

    clinical_rows = _read_csv(clinical_path)
    additional_rows = _read_csv(additional_path)
    solicited_rows = _read_csv(solicited_path)
    clinical_by_id = {row.get("participant", "").strip(): row for row in clinical_rows}
    additional_by_id = {row.get("participant", "").strip(): row for row in additional_rows}
    audio_index = _audio_index(Path(audio_root))
    paths_by_patient: dict[str, list[Path]] = {}
    for row in solicited_rows:
        patient_id = row.get("participant", "").strip()
        filename = Path(row.get("filename", "")).name
        if not patient_id or not filename:
            continue
        audio_path = audio_index.get(filename.casefold())
        if audio_path is not None:
            paths_by_patient.setdefault(patient_id, []).append(audio_path)

    examples: list[PatientExample] = []
    for patient_id, clinical in clinical_by_id.items():
        if not patient_id or patient_id not in paths_by_patient:
            continue
        additional = additional_by_id.get(patient_id)
        if additional is None:
            continue
        payload = _build_payload(clinical, additional)
        label = _parse_reference_label(
            additional.get("Microbiologicreferencestandard")
        )
        paths = tuple(paths_by_patient[patient_id][:max_clips])
        if paths:
            examples.append(PatientExample(patient_id, label, paths, payload))

    if not examples:
        raise DatasetError("no patients have both valid metadata and audio")
    return examples
