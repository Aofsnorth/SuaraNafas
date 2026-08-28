"""Download the TBscreen cough audio subset used for from-scratch training.

Only the audio files listed in the dataset CSVs with Permission_sound == "Yes"
and a usable TB/NTB label are fetched, via HTTP range requests against the
public S3 archive (no full 395 GB download).
"""

from __future__ import annotations

import csv
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from remotezip import RemoteZip

ZIP_URL = "https://tbscreen.s3.amazonaws.com/TBscreen_Dataset.zip"
DATA_ROOT = Path("data/tbscreen/TBscreen_Dataset")
FORCED_CSV = DATA_ROOT / "Forced_coughs/Forced_coughs.csv"
PASSIVE_CSV = DATA_ROOT / "Passive_coughs/Passive_coughs.csv"
PASSIVE_CLIPS_PER_SUBJECT = 20
WORKERS = 4
ARCHIVE_ROOT = "TBscreen_Dataset/"


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.DictReader(handle) if row.get("Label") in {"TB", "NTB"} and row.get("Permission_sound") == "Yes"]


def plan_downloads(zip_names: set[str]) -> list[str]:
    forced_prefix = "TBscreen_Dataset/Forced_coughs/Audio_files/"
    passive_prefix = "TBscreen_Dataset/Passive_coughs/Audio_files/"

    wanted: set[str] = set()
    for row in _load_rows(FORCED_CSV):
        candidate = f"{forced_prefix}{row['path']}.wav"
        if candidate in zip_names:
            wanted.add(candidate)

    per_subject: dict[str, list[str]] = {}
    for row in _load_rows(PASSIVE_CSV):
        candidate = f"{passive_prefix}{row['path']}.wav"
        if candidate in zip_names:
            per_subject.setdefault(row["subject"], []).append(candidate)
    for candidates in per_subject.values():
        wanted.update(sorted(candidates)[:PASSIVE_CLIPS_PER_SUBJECT])

    return sorted(wanted)


def extracted_path(archive_name: str) -> Path:
    """Resolve a TBscreen archive member to its local extracted path."""
    if not archive_name.startswith(ARCHIVE_ROOT):
        raise ValueError("archive member must be under TBscreen_Dataset")
    return DATA_ROOT / archive_name.removeprefix(ARCHIVE_ROOT)


def main() -> None:
    with RemoteZip(ZIP_URL) as archive:
        wanted = plan_downloads(set(archive.namelist()))
    print(f"planned downloads: {len(wanted)}", flush=True)

    todo = [name for name in wanted if not extracted_path(name).exists()]
    print(f"remaining: {len(todo)}", flush=True)

    shards = [todo[index::WORKERS] for index in range(WORKERS)]
    progress_lock = threading.Lock()
    completed = 0

    def worker(shard: list[str]) -> None:
        nonlocal completed
        if not shard:
            return
        with RemoteZip(ZIP_URL) as archive:
            for name in shard:
                if not name.startswith(ARCHIVE_ROOT) or ".." in Path(name).parts:
                    raise ValueError("unsafe archive member path")
                archive.extract(name, "data/tbscreen")
                with progress_lock:
                    completed += 1
                    if completed % 200 == 0:
                        print(f"progress: {completed}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(worker, shards))
    print(f"done: {completed} files extracted")

    manifest = {"zip_url": ZIP_URL, "files": wanted}
    (DATA_ROOT / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest written with {len(wanted)} entries")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
