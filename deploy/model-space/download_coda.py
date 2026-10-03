"""Download the CODA-TB DREAM screening dataset from Synapse.

CODA-TB is published under CC-BY 4.0 and allows commercial use, but access is
gated: you need a Synapse account, a *Certified & Validated* profile, an
Intended Data Use statement (<= 500 words) and acceptance of the terms. This
script therefore refuses to run until ``SYNAPSE_AUTH_TOKEN`` is present and it
never fabricates a result if the remote layout differs from what it expects.

Requested scope
---------------
The full dataset is ~745 GB because every visit is recorded longitudinally.
The first-pass research target is the **solicited** recording partition, which
is roughly 0.4 GB for the ~1105 training participants. Pass
``--include-longitudinal`` only if that analysis is actually needed.

Everything lands under ``--destination`` (default ``coda-tb``) and must stay
outside version control; check ``.gitignore`` before committing.

Usage
-----
    export SYNAPSE_AUTH_TOKEN=...
    python download_coda.py --destination coda-tb
    python download_coda.py --dry-run          # list what would be fetched
    python download_coda.py --limit-participants 200
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path


SYNAPSE_FOLDER_ID = "syn40358494"
SYNAPSE_METADATA_ID = "syn41604939"
METADATA_FILENAMES = ("clinical.csv", "additional.csv", "solicited.csv")


def _fail(message: str) -> "SystemExit":
    print(f"error: {message}", file=sys.stderr)
    return SystemExit(1)


def _require_synapse_client():
    try:
        import synapseclient
    except ImportError:
        raise _fail(
            "synapseclient is not installed. Install it in a data-download "
            "environment (not in the model runtime): pip install synapseclient"
        ) from None
    return synapseclient


def _login(synapseclient_module):
    token = os.getenv("SYNAPSE_AUTH_TOKEN", "").strip()
    if not token:
        raise _fail(
            "SYNAPSE_AUTH_TOKEN is not set.\n"
            "  1. Create a Synapse account and complete Certified & Validated status.\n"
            "  2. Open https://www.synapse.org/Synapse:syn50353157 and accept the terms.\n"
            "  3. Create a personal access token (Settings > Personal Access Tokens).\n"
            "  4. export SYNAPSE_AUTH_TOKEN=<your token>"
        )
    client = synapseclient_module.Synapse(silent=True)
    try:
        client.login(authToken=token)
    except Exception as error:  # noqa: BLE001 - surface Synapse's own message
        raise _fail(f"Synapse login failed: {error}") from error
    return client


def download_metadata(client, destination: Path) -> Path:
    """Fetch the CSV bundle that defines labels and clinical variables."""
    destination.mkdir(parents=True, exist_ok=True)
    try:
        client.get(SYNAPSE_METADATA_ID, downloadLocation=str(destination))
    except Exception as error:  # noqa: BLE001
        raise _fail(f"could not download CODA-TB metadata ({SYNAPSE_METADATA_ID}): {error}") from error

    missing = [name for name in METADATA_FILENAMES if not (destination / name).is_file()]
    if missing:
        raise _fail(
            f"metadata download finished but {missing} are missing from {destination}. "
            "The Synapse layout may have changed; re-check the dataset page before "
            "relying on the loader."
        )
    return destination


def _wanted_filenames(destination: Path, *, include_longitudinal: bool) -> set[str]:
    """Read the requested audio filenames out of the metadata CSVs."""
    import csv

    names: set[str] = set()
    for csv_name, column in (
        ("solicited.csv", "filename"),
        ("visit_control.csv", "filename"),
    ):
        path = destination / csv_name
        if not path.is_file():
            continue
        if csv_name == "visit_control.csv" and not include_longitudinal:
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or column not in reader.fieldnames:
                continue
            for row in reader:
                value = (row.get(column) or "").strip()
                if value:
                    names.add(value)
    if not names:
        raise _fail(
            "no audio filenames were found in the metadata. Expected a 'filename' "
            "column in solicited.csv."
        )
    return names


def _entity_field(entity, field: str):
    """Read one field from a Synapse child entry.

    ``getChildren`` returns plain dicts in synapseclient 4.x while older
    releases return objects with attributes. Reading only via getattr therefore
    silently yields nothing against the current real API, which is the worst
    possible failure mode for a downloader: it reports success and fetches
    nothing. Both shapes are supported here.
    """
    if isinstance(entity, dict):
        return entity.get(field)
    value = getattr(entity, field, None)
    if value is not None:
        return value
    try:
        return entity[field]
    except (TypeError, KeyError, IndexError):
        return None


def _is_folder_entity(entity) -> bool:
    """Real Synapse folders are ``org.sagebionetworks.repo.model.FolderEntity``,
    not a literal ``FOLDER`` type string."""
    kind = _entity_field(entity, "type") or _entity_field(entity, "concreteType") or ""
    return "folder" in str(kind).lower()


def _iter_remote_files(client, parent_id: str) -> Iterable[tuple[str, str]]:
    """Yield ``(syn_id, filename)`` for every file entity under ``parent_id``."""
    pending = [parent_id]
    while pending:
        current = pending.pop()
        try:
            children = list(client.getChildren(current))
        except Exception as error:  # noqa: BLE001
            print(f"warning: could not list {current}: {error}", file=sys.stderr)
            continue
        for child in children:
            if _is_folder_entity(child):
                folder_id = _entity_field(child, "id")
                if folder_id is None:
                    folder_name = _entity_field(child, "name")
                    if isinstance(folder_name, str) and folder_name.startswith("syn"):
                        folder_id = folder_name
                if folder_id is not None:
                    pending.append(folder_id)
                continue
            name = _entity_field(child, "name")
            identifier = _entity_field(child, "id")
            if name is None and isinstance(identifier, str) and identifier.startswith("syn"):
                name, identifier = identifier, None
            if identifier is not None:
                yield identifier, name or ""


def _resolve_download_target(client, identifier: str, filename: str, destination: Path) -> Path:
    """Map a remote file to its canonical CODA-TB relative sub-directory.

    The sub-directory is reproduced because the training loader joins remote
    paths against the audio root. Remote names are still untrusted input:
    a traversal segment or an absolute path would write outside the
    destination, so both are rejected rather than normalised.
    """
    name = (filename or "").strip().replace("\\", "/")
    if not name:
        raise _fail(f"file {identifier} has no usable name")
    parts = [part for part in name.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise _fail(
            f"refusing to write {filename!r} outside {destination}: the name "
            "contains a parent-directory segment"
        )
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise _fail(f"refusing to write {filename!r}: absolute paths are not allowed")
    return destination.joinpath(*parts)


def _participant_for_filename(destination: Path, filename: str) -> str | None:
    """Map an audio filename back to its participant via the metadata tables.

    Counting files instead of participants is what makes a "--limit-participants"
    flag quietly overshoot: CODA-TB participants contribute anywhere from a
    couple of clips to several dozen, so a file count is not a participant count.
    """
    import csv

    for csv_name in ("solicited.csv", "visit_control.csv"):
        path = destination / csv_name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "filename" not in reader.fieldnames:
                continue
            if "participant" not in reader.fieldnames:
                continue
            for row in reader:
                value = (row.get("filename") or "").strip()
                if value and (value == filename or value.rsplit("/", 1)[-1] == filename.rsplit("/", 1)[-1]):
                    participant = (row.get("participant") or "").strip()
                    if participant:
                        return participant
    return None


def download_audio(
    client,
    destination: Path,
    *,
    include_longitudinal: bool,
    limit_participants: int | None,
    dry_run: bool,
) -> int:
    wanted = _wanted_filenames(destination, include_longitudinal=include_longitudinal)
    print(f"requested audio files: {len(wanted)}")
    if limit_participants is not None and limit_participants <= 0:
        raise _fail("--limit-participants must be a positive number")

    if dry_run:
        for name in sorted(wanted)[:20]:
            print(f"  would fetch {name}")
        if len(wanted) > 20:
            print(f"  ... and {len(wanted) - 20} more")
        return 0

    downloaded = 0
    skipped = 0
    seen_participants: set[str] = set()
    truncated = False
    for identifier, filename in _iter_remote_files(client, SYNAPSE_FOLDER_ID):
        basename = (filename or "").rsplit("/", 1)[-1]
        if not filename or (filename not in wanted and basename not in wanted):
            continue
        participant = _participant_for_filename(destination, filename)
        if (
            limit_participants is not None
            and participant is not None
            and participant not in seen_participants
            and len(seen_participants) >= limit_participants
        ):
            truncated = True
            break
        if participant is not None:
            seen_participants.add(participant)
        target = _resolve_download_target(client, identifier, filename, destination)
        if target.is_file() and target.stat().st_size > 0:
            skipped += 1
            continue
        try:
            client.get(identifier, downloadLocation=str(target.parent))
        except Exception as error:  # noqa: BLE001
            print(f"warning: {filename or identifier} failed: {error}", file=sys.stderr)
            continue
        downloaded += 1
        if downloaded % 100 == 0:
            print(f"  downloaded {downloaded} files", flush=True)

    print(
        f"downloaded {downloaded} files from {len(seen_participants)} participants, "
        f"skipped {skipped} already present"
    )
    if truncated:
        print(
            f"stopped at the --limit-participants={limit_participants} cap; "
            "re-run with a larger limit to continue"
        )
    if downloaded == 0 and skipped == 0:
        raise _fail(
            "no audio files matched. The remote folder layout may differ from the "
            "documented CODA-TB structure; inspect it with "
            "python -c \"import synapseclient as s; c=s.Synapse(); c.login(); "
            "print(list(c.getChildren('%s'))[:20])\"" % SYNAPSE_FOLDER_ID
        )
    return downloaded


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.getenv("CODA_DATA_DIR", "coda-tb")),
        help="Directory for metadata and audio (kept out of version control)",
    )
    parser.add_argument(
        "--include-longitudinal",
        action="store_true",
        help="Also fetch visit-control recordings (~31.6 GB) instead of only solicited",
    )
    parser.add_argument(
        "--limit-participants",
        type=int,
        default=None,
        help="Stop after roughly this many participants (use to trial the download)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List files, download nothing")
    args = parser.parse_args(argv)

    synapseclient = _require_synapse_client()
    destination = args.destination.resolve()
    client = _login(synapseclient)

    print(f"downloading CODA-TB metadata into {destination}")
    download_metadata(client, destination)
    print(f"metadata ready: {[name for name in METADATA_FILENAMES]}")

    download_audio(
        client,
        destination,
        include_longitudinal=args.include_longitudinal,
        limit_participants=args.limit_participants,
        dry_run=args.dry_run,
    )
    print(
        "\nNext step: point the fusion trainer at the downloaded CSVs, e.g.\n"
        "  python -m training.cross_validate_fusion \\\n"
        "    --clinical-metadata coda-tb/clinical.csv \\\n"
        "    --additional-metadata coda-tb/additional.csv \\\n"
        "    --solicited-metadata coda-tb/solicited.csv \\\n"
        "    --audio-root coda-tb"
    )


if __name__ == "__main__":
    main()
