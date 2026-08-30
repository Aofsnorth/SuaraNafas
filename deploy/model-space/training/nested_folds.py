from __future__ import annotations

import csv
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from training.dataset import DatasetError


Record = TypeVar("Record")


@dataclass(frozen=True)
class NestedPartition(Generic[Record]):
    outer_fold: int
    inner_fold: int
    train: tuple[Record, ...]
    validation: tuple[Record, ...]
    test: tuple[Record, ...]


def _patient_id(record: Record) -> str:
    value = getattr(record, "patient_id", None)
    if not isinstance(value, str) or not value:
        raise TypeError("Each record must have a non-empty patient_id")
    return value


def _label(record: Record) -> int:
    value = getattr(record, "label", None)
    if value not in (0, 1):
        raise TypeError("Each record must have a binary integer label")
    return value


def _read_fold_subjects(path: Path) -> dict[str, int]:
    subjects: dict[str, int] = {}
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = csv.DictReader(handle)
            if rows.fieldnames is None or not {"subject", "class"} <= set(rows.fieldnames):
                raise DatasetError("fold CSV must contain subject and class columns")
            for row in rows:
                subject = str(row.get("subject", "")).strip()
                label_value = str(row.get("class", "")).strip()
                if not subject or label_value not in {"0", "1"}:
                    raise DatasetError("fold CSV contains an invalid subject or class")
                label = int(label_value)
                previous = subjects.setdefault(subject, label)
                if previous != label:
                    raise DatasetError("fold CSV contains conflicting subject labels")
    except (OSError, csv.Error) as error:
        raise DatasetError(f"could not read official fold CSV: {path}") from error
    if not subjects:
        raise DatasetError("fold CSV contains no subjects")
    return subjects


def load_official_subject_folds(
    fold_paths: Sequence[str | Path],
    records: Sequence[Record],
) -> tuple[tuple[Record, ...], ...]:
    """Map local consented records onto disjoint official TBscreen subject folds."""
    if len(fold_paths) < 3:
        raise ValueError("at least three official folds are required")
    records_by_id: dict[str, Record] = {}
    for record in records:
        patient_id = _patient_id(record)
        if patient_id in records_by_id:
            raise ValueError("patient records must be unique")
        records_by_id[patient_id] = record

    assigned_subjects: set[str] = set()
    folds: list[tuple[Record, ...]] = []
    for fold_path in fold_paths:
        official_subjects = _read_fold_subjects(Path(fold_path))
        overlap = assigned_subjects & set(official_subjects)
        if overlap:
            raise DatasetError("official folds contain overlapping subjects")
        assigned_subjects.update(official_subjects)
        matched = tuple(
            records_by_id[subject]
            for subject in sorted(official_subjects)
            if subject in records_by_id
        )
        if any(_label(record) != official_subjects[_patient_id(record)] for record in matched):
            raise DatasetError("local and official fold labels disagree")
        if {_label(record) for record in matched} != {0, 1}:
            raise DatasetError("each local official fold must contain both classes")
        folds.append(matched)
    return tuple(folds)


def build_nested_partitions(
    folds: Sequence[Sequence[Record]],
) -> tuple[NestedPartition[Record], ...]:
    """Create every inner validation split while keeping each outer fold untouched."""
    if len(folds) < 3:
        raise ValueError("at least three folds are required")
    fold_ids = [{_patient_id(record) for record in fold} for fold in folds]
    if any(not identifiers for identifiers in fold_ids):
        raise ValueError("folds must not be empty")
    for left_index, left_ids in enumerate(fold_ids):
        for right_ids in fold_ids[left_index + 1 :]:
            if not left_ids.isdisjoint(right_ids):
                raise ValueError("subject folds must be disjoint")

    partitions: list[NestedPartition[Record]] = []
    for outer_index, outer_test in enumerate(folds):
        for inner_index, validation in enumerate(folds):
            if inner_index == outer_index:
                continue
            train = tuple(
                record
                for fold_index, fold in enumerate(folds)
                if fold_index not in {outer_index, inner_index}
                for record in fold
            )
            partitions.append(
                NestedPartition(
                    outer_fold=outer_index,
                    inner_fold=inner_index,
                    train=train,
                    validation=tuple(validation),
                    test=tuple(outer_test),
                )
            )
    return tuple(partitions)


def summarize_fold(records: Sequence[Record]) -> dict[str, int | str]:
    patient_ids = sorted(_patient_id(record) for record in records)
    digest = hashlib.sha256("\n".join(patient_ids).encode("utf-8")).hexdigest()
    return {
        "subjects": len(records),
        "tb": sum(_label(record) == 1 for record in records),
        "non_tb": sum(_label(record) == 0 for record in records),
        "subject_id_sha256": digest,
    }


def official_fold_file_hashes(fold_paths: Sequence[str | Path]) -> tuple[str, ...]:
    hashes: list[str] = []
    for fold_path in fold_paths:
        digest = hashlib.sha256()
        try:
            with Path(fold_path).open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise DatasetError(f"could not hash official fold CSV: {fold_path}") from error
        hashes.append(digest.hexdigest())
    return tuple(hashes)
