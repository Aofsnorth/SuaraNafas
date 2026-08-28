from __future__ import annotations

from training.split import split_by_patient
from tests.factories import build_patient_records


def test_split_keeps_each_patient_in_exactly_one_partition() -> None:
    records = build_patient_records()
    partitions = split_by_patient(records, seed=17, validation_fraction=0.25, test_fraction=0.25)

    train_ids = {record.patient_id for record in partitions.train}
    validation_ids = {record.patient_id for record in partitions.validation}
    test_ids = {record.patient_id for record in partitions.test}

    assert train_ids.isdisjoint(validation_ids)
    assert train_ids.isdisjoint(test_ids)
    assert validation_ids.isdisjoint(test_ids)
    assert train_ids | validation_ids | test_ids == {record.patient_id for record in records}


def test_split_is_deterministic_for_same_seed() -> None:
    records = build_patient_records()

    first = split_by_patient(records, seed=17, validation_fraction=0.25, test_fraction=0.25)
    second = split_by_patient(records, seed=17, validation_fraction=0.25, test_fraction=0.25)

    assert first == second


def test_split_preserves_both_classes_when_dataset_allows_it() -> None:
    partitions = split_by_patient(
        build_patient_records(),
        seed=17,
        validation_fraction=0.25,
        test_fraction=0.25,
    )

    assert {record.label for record in partitions.train} == {0, 1}
    assert {record.label for record in partitions.validation} == {0, 1}
    assert {record.label for record in partitions.test} == {0, 1}
