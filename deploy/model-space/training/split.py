from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar


Record = TypeVar("Record")


@dataclass(frozen=True)
class PatientPartitions(Generic[Record]):
    train: tuple[Record, ...]
    validation: tuple[Record, ...]
    test: tuple[Record, ...]


def _class_buckets(records: Sequence[Record]) -> dict[int, list[Record]]:
    buckets: dict[int, list[Record]] = {}
    for record in records:
        label = getattr(record, "label", None)
        if not isinstance(label, int):
            raise TypeError("Each patient record must have an integer label")
        buckets.setdefault(label, []).append(record)
    if len(buckets) < 2:
        raise ValueError("At least two label classes are required")
    return buckets


def _partition_bucket(
    bucket: list[Record],
    validation_count: int,
    test_count: int,
    rng: random.Random,
) -> tuple[list[Record], list[Record], list[Record]]:
    shuffled = list(bucket)
    rng.shuffle(shuffled)
    test = shuffled[:test_count]
    validation = shuffled[test_count : test_count + validation_count]
    train = shuffled[test_count + validation_count :]
    return train, validation, test


def split_by_patient(
    records: Sequence[Record],
    *,
    seed: int,
    validation_fraction: float,
    test_fraction: float,
) -> PatientPartitions[Record]:
    """Create deterministic stratified partitions without splitting a patient."""
    if not records:
        raise ValueError("At least one patient record is required")
    if validation_fraction <= 0 or test_fraction <= 0:
        raise ValueError("Validation and test fractions must be positive")
    if validation_fraction + test_fraction >= 1:
        raise ValueError("Validation and test fractions must sum to less than one")

    buckets = _class_buckets(records)
    rng = random.Random(seed)
    train: list[Record] = []
    validation: list[Record] = []
    test: list[Record] = []
    for bucket in buckets.values():
        minimum_required = 3
        if len(bucket) < minimum_required:
            raise ValueError("Each label class needs at least three patients")
        validation_count = max(1, round(len(bucket) * validation_fraction))
        test_count = max(1, round(len(bucket) * test_fraction))
        if validation_count + test_count >= len(bucket):
            raise ValueError("Fractions leave no patient for the training partition")
        bucket_train, bucket_validation, bucket_test = _partition_bucket(
            bucket,
            validation_count,
            test_count,
            rng,
        )
        train.extend(bucket_train)
        validation.extend(bucket_validation)
        test.extend(bucket_test)

    return PatientPartitions(tuple(train), tuple(validation), tuple(test))
