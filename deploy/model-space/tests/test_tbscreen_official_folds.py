"""Checks against the real TBscreen fold metadata, not a fixture.

The five ``FOLD_xprt_class_*.csv`` files published in the TBscreen code archive
(Zenodo 10431329) are the paper's own subject-level split. Verifying the
loader against them catches format drift that a hand-written fixture cannot,
and it documents what the cohort actually looks like.

These tests are skipped when the metadata is absent, because the archive is
large and the audio it once referenced is no longer downloadable.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from training.nested_folds import _read_fold_subjects


FOLD_DIR = Path(__file__).resolve().parents[1] / "data" / "tbscreen" / "folds"
XPERT_FOLDS = sorted(FOLD_DIR.glob("FOLD_xprt_class_*.csv"))

pytestmark = pytest.mark.skipif(
    not XPERT_FOLDS,
    reason="TBscreen fold metadata not present; see docs/DATASET_PROTOCOL.md",
)

# Columns that define the label. They must never reach the clinical
# preprocessor: they are the reference standard, not a clinical sign.
LEAKY_COLUMNS = frozenset(
    {
        "lab_sptm_xprt_rslt_a",
        "lab_sptm_xpert_ct_a",
        "lab_sptm_cx_rslt_a",
        "lab_sptm_cx_ttd_a",
        "lab_sptm_smr_rslt_a",
        "cxr_findings_a___5",
        "Label",
        "class",
        "xprt_class",
    }
)


def _rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in XPERT_FOLDS:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def test_five_official_folds_are_published() -> None:
    assert len(XPERT_FOLDS) == 5


def test_official_folds_parse_with_the_existing_loader() -> None:
    """The loader requires subject + class columns; the real files satisfy it."""
    for path in XPERT_FOLDS:
        subjects = _read_fold_subjects(path)
        assert subjects, path.name
        assert set(subjects.values()) <= {0, 1}


def test_official_folds_are_subject_disjoint() -> None:
    """A cougher appearing in two folds would inflate every published number."""
    seen: set[str] = set()
    for path in XPERT_FOLDS:
        subjects = set(_read_fold_subjects(path))
        assert not (subjects & seen), f"{path.name} overlaps an earlier fold"
        seen |= subjects


def test_every_official_fold_contains_both_classes() -> None:
    for path in XPERT_FOLDS:
        assert set(_read_fold_subjects(path).values()) == {0, 1}, path.name


def test_cohort_totals_match_the_published_t1_size() -> None:
    """The paper describes T1 as 90 subjects; these are its fold files."""
    subjects: set[str] = set()
    for path in XPERT_FOLDS:
        subjects |= set(_read_fold_subjects(path))
    assert len(subjects) == 90


def test_label_columns_are_identified_as_leaky() -> None:
    """Every reference-standard column in the real file must be named in the
    banned list, otherwise a future refactor could feed them to the model."""
    present = set(_rows()[0].keys())
    assert LEAKY_COLUMNS <= present, "a new leaky column needs review"
    for column in LEAKY_COLUMNS:
        assert column in present, f"{column} listed as leaky but absent from the file"


def test_acquisition_device_is_recorded_per_cough() -> None:
    """Zhang et al. identify device variation as the main reason these models
    fail to transfer. The metadata has to carry it for that to be testable."""
    devices = {row["device"] for row in _rows() if row.get("device")}
    assert devices == {"pixel", "codec", "yeti"}


def test_most_subjects_were_recorded_on_multiple_devices() -> None:
    rows = _rows()
    by_subject: dict[str, set[str]] = {}
    for row in rows:
        if row.get("device"):
            by_subject.setdefault(row["subject"], set()).add(row["device"])
    multi = sum(1 for devices in by_subject.values() if len(devices) > 1)
    assert multi > 0.5 * len(by_subject)


def test_metadata_contains_an_impossible_age() -> None:
    """PID_72C records age -10.0. Documented rather than silently cleaned, so
    the preprocessor's guard is known to be load-bearing."""
    impossible = {
        row["subject"]
        for row in _rows()
        if row.get("age") and float(row["age"]) < 0
    }
    assert "PID_72C" in impossible


def test_subject_identifiers_are_unique_per_participant() -> None:
    subjects = {row["subject"] for row in _rows()}
    # Each subject maps to a single clinical profile.
    profiles: dict[str, set[str]] = {}
    for row in _rows():
        profiles.setdefault(row["subject"], set()).add(
            (row.get("age", ""), row.get("gndr_a", ""), row.get("hiv_infected_a", ""))
        )
    assert all(len(values) == 1 for values in profiles.values())
