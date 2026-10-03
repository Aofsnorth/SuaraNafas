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


# CODA's metadata uses the literal string "NA" for a missing measurement rather
# than an empty cell. Verified against CODA_TB_Clinical_Meta_Info.csv, where
# height is recorded as "NA" for one participant. Treating it as a number
# aborted the whole 1,105-participant load; treating it as absent lets the
# preprocessor impute from the training partition instead.
MISSING_SENTINELS = frozenset({"", "NA", "N/A", "NAN", "NONE", "NULL", "-", "UNKNOWN"})


def _is_missing(raw: Any) -> bool:
    return str(raw if raw is not None else "").strip().upper() in MISSING_SENTINELS


def _build_payload(clinical: dict[str, str], additional: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {**clinical, **additional}
    for field in _numeric_fields():
        raw = payload.get(field, "")
        if _is_missing(raw):
            payload[field] = ""
            continue
        try:
            payload[field] = float(raw)
        except (TypeError, ValueError) as error:
            raise DatasetError(f"field {field} is not numeric: {raw!r}") from error
    # CODA leaves HIVstatus blank for a few participants. "Unknown" is a real
    # category in the encoder's feature set, so a missing result is recorded
    # as unknown rather than treated as an error or silently read as negative.
    if _is_missing(payload.get("HIVstatus")):
        payload["HIVstatus"] = "Unknown"
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


def _spread_sample(items: Sequence[Path], limit: int) -> list[Path]:
    """Take at most ``limit`` items spread evenly across ``items``.

    Solicited and longitudinal clips are concatenated in one list, so capping
    from the head would spend the whole budget on the first source and leave
    the other unused. Spreading keeps a representative sample of both.
    """
    if len(items) <= limit:
        return list(items)
    if limit < 1:
        return []
    if limit == 1:
        return [items[0]]
    # Both endpoints are kept so a capped list still spans the whole input;
    # an index-only stride leaves the tail out of the sample.
    last = len(items) - 1
    return [items[round(index * last / (limit - 1))] for index in range(limit)]


def load_patient_examples(
    clinical_path: str | Path,
    additional_path: str | Path,
    solicited_path: str | Path,
    audio_root: str | Path,
    *,
    max_clips: int,
    longitudinal_metadata: str | Path | None = None,
    longitudinal_audio_root: str | Path | None = None,
) -> list[PatientExample]:
    """Join CODA metadata and audio while keeping all clips grouped by patient.

    ``longitudinal_metadata`` is optional. CODA records prompted (solicited)
    coughs and natural (longitudinal) coughs; the latter are much closer to
    how a phone is actually used, so they are worth training on. They are
    mixed with the solicited clips rather than appended, because a head-based
    ``max_clips`` cap would otherwise keep only solicited audio.
    """
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

    # Natural (longitudinal) coughs, collected without prompting. They sit in a
    # separate root and a separate index because the two releases are shipped
    # apart and a shared index would reject legitimately distinct basenames.
    longitudinal_by_patient: dict[str, list[Path]] = {}
    if longitudinal_metadata is not None:
        if longitudinal_audio_root is None:
            raise DatasetError("longitudinal_audio_root is required with longitudinal_metadata")
        long_index = _audio_index(Path(longitudinal_audio_root))
        for row in _read_csv(longitudinal_metadata):
            patient_id = row.get("participant", "").strip()
            filename = Path(row.get("filename", "")).name
            if not patient_id or not filename:
                continue
            audio_path = long_index.get(filename.casefold())
            if audio_path is not None:
                longitudinal_by_patient.setdefault(patient_id, []).append(audio_path)
        print(
            f"note: loaded {sum(len(v) for v in longitudinal_by_patient.values())} "
            f"longitudinal clips for {len(longitudinal_by_patient)} participant(s)",
            flush=True,
        )

    examples: list[PatientExample] = []
    unlabelled: list[str] = []
    missing_audio: list[str] = []
    for patient_id, clinical in clinical_by_id.items():
        if not patient_id:
            continue
        if not (
            patient_id in paths_by_patient or patient_id in longitudinal_by_patient
        ):
            missing_audio.append(patient_id)
            continue
        additional = additional_by_id.get(patient_id)
        if additional is None:
            continue
        payload = _build_payload(clinical, additional)
        # A participant with no microbiological result cannot be labelled.
        # That is a data gap, not a reason to abandon the other thousand, but
        # it must be reported rather than dropped silently.
        try:
            label = _parse_reference_label(
                additional.get("Microbiologicreferencestandard")
            )
        except DatasetError:
            unlabelled.append(patient_id)
            continue
        # Solicited and natural coughs are interleaved before the cap is
        # applied, so the budget is not spent entirely on prompted audio.
        merged = tuple(paths_by_patient.get(patient_id, [])) + tuple(
            longitudinal_by_patient.get(patient_id, [])
        )
        paths = tuple(_spread_sample(list(merged), max_clips))
        if paths:
            examples.append(PatientExample(patient_id, label, paths, payload))

    if not examples:
        raise DatasetError("no patients have both valid metadata and audio")
    if unlabelled:
        print(
            f"note: skipped {len(unlabelled)} participant(s) with no microbiological "
            f"reference standard: {', '.join(sorted(unlabelled)[:10])}"
            + (" ..." if len(unlabelled) > 10 else ""),
            flush=True,
        )
    if missing_audio:
        print(
            f"note: {len(missing_audio)} participant(s) had no audio in the download "
            "(the mirror is incomplete; the Synapse release is the full set)",
            flush=True,
        )
    return examples


def read_solicited_participants(solicited_path: str | Path) -> set[str]:
    """Participants that have at least one prompted (solicited) recording.

    Longitudinal audio introduces participants who never recorded a prompted
    clip. Comparing a run that includes them against one that does not would
    compare two different fold shuffles rather than two models, so a cohort can
    be pinned to the prompted set on purpose.
    """
    return {
        row.get("participant", "").strip()
        for row in _read_csv(solicited_path)
        if row.get("participant", "").strip()
    }
