from __future__ import annotations

import csv
import json

import pytest

from training.dataset import DatasetError
from training.nested_folds import (
    build_nested_partitions,
    load_official_subject_folds,
    official_fold_file_hashes,
    summarize_fold,
)
from tests.factories import PatientRecord, build_fold_patient_records


def _write_fold_csvs(tmp_path, records: list[PatientRecord], fold_count: int = 5):
    paths = []
    for fold_index in range(fold_count):
        path = tmp_path / f"T1_{fold_index}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("subject", "class"))
            writer.writeheader()
            for record in records:
                if record.patient_id.startswith(f"fold-{fold_index}-"):
                    writer.writerow(
                        {"subject": record.patient_id, "class": record.label}
                    )
        paths.append(path)
    return paths


def test_nested_partitions_keep_outer_test_subjects_untouched(tmp_path) -> None:
    records = build_fold_patient_records()
    paths = _write_fold_csvs(tmp_path, records)

    folds = load_official_subject_folds(paths, records)
    partitions = build_nested_partitions(folds)

    assert len(partitions) == 20
    for partition in partitions:
        train_ids = {record.patient_id for record in partition.train}
        validation_ids = {record.patient_id for record in partition.validation}
        test_ids = {record.patient_id for record in partition.test}
        assert train_ids.isdisjoint(validation_ids)
        assert train_ids.isdisjoint(test_ids)
        assert validation_ids.isdisjoint(test_ids)
        assert {record.label for record in partition.train} == {0, 1}
        assert {record.label for record in partition.validation} == {0, 1}
        assert {record.label for record in partition.test} == {0, 1}


def test_official_fold_mapping_is_deterministic_and_checks_labels(tmp_path) -> None:
    records = build_fold_patient_records()
    paths = _write_fold_csvs(tmp_path, records)

    first = load_official_subject_folds(paths, records)
    second = load_official_subject_folds(paths, list(reversed(records)))

    assert first == second
    mismatched = [PatientRecord(records[0].patient_id, 1), *records[1:]]
    with pytest.raises(DatasetError, match="labels disagree"):
        load_official_subject_folds(paths, mismatched)


def test_fold_report_contains_hashes_without_patient_identifiers(tmp_path) -> None:
    records = build_fold_patient_records()
    paths = _write_fold_csvs(tmp_path, records)
    folds = load_official_subject_folds(paths, records)

    report = {
        "fold": summarize_fold(folds[0]),
        "source_sha256": official_fold_file_hashes(paths),
    }
    serialized = json.dumps(report)

    assert report["fold"]["subjects"] == 2
    assert len(report["source_sha256"]) == 5
    assert all(record.patient_id not in serialized for record in records)
