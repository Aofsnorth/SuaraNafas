from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatientRecord:
    patient_id: str
    label: int


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
