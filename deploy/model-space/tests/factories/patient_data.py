from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatientRecord:
    patient_id: str
    label: int


def build_fold_patient_records(fold_count: int = 5) -> list[PatientRecord]:
    return [
        PatientRecord(f"fold-{fold_index}-class-{label}", label)
        for fold_index in range(fold_count)
        for label in (0, 1)
    ]


def build_patient_records() -> list[PatientRecord]:
    return [
        PatientRecord("patient-01", 0),
        PatientRecord("patient-02", 0),
        PatientRecord("patient-03", 0),
        PatientRecord("patient-04", 0),
        PatientRecord("patient-05", 1),
        PatientRecord("patient-06", 1),
        PatientRecord("patient-07", 1),
        PatientRecord("patient-08", 1),
    ]
