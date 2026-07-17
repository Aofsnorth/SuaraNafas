from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import shutil
from threading import local
import time

import synapseclient


DESTINATION = Path(__file__).resolve().parents[2] / "data" / "coda-tb"
SOLICITED_FOLDER_ID = "syn40358494"
SOLICITED_METADATA_ID = "syn41604939"
DOWNLOAD_WORKERS = 1000
MAX_RETRIES = 3
LOCAL_METADATA_FILES = (
    "CODA_TB_Clinical_Meta_Info.csv",
    "CODA_TB_additional_variables_train.csv",
)

_worker_state = local()


def create_client(token: str, *, silent: bool) -> synapseclient.Synapse:
    synapse = synapseclient.Synapse(silent=silent)
    synapse.login(authToken=token)
    return synapse


def worker_client(token: str) -> synapseclient.Synapse:
    client = getattr(_worker_state, "client", None)
    if client is None:
        client = create_client(token, silent=True)
        _worker_state.client = client
    return client


def collect_downloads(
    synapse: synapseclient.Synapse,
    folder_id: str,
) -> list[tuple[str, Path, Path]]:
    pending = deque([(folder_id, DESTINATION / "solicited_data")])
    downloads: list[tuple[str, Path, Path]] = []

    while pending:
        parent_id, parent_path = pending.popleft()
        parent_path.mkdir(parents=True, exist_ok=True)

        for child in synapse.getChildren(parent_id):
            child_type = child.get("type", "")
            child_name = child["name"]
            child_id = child["id"]
            if "Folder" in child_type:
                pending.append((child_id, parent_path / child_name))
            elif "File" in child_type:
                target = parent_path / child_name
                if not target.exists() or target.stat().st_size == 0:
                    downloads.append((child_id, parent_path, target))

    return downloads


def download_file(
    token: str,
    entity_id: str,
    parent_path: Path,
    target: Path,
) -> bool:
    if target.exists() and target.stat().st_size > 0:
        return False

    parent_path.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            worker_client(token).get(entity_id, downloadLocation=str(parent_path))
            if target.exists() and target.stat().st_size > 0:
                return True
            raise RuntimeError(f"Downloaded file is missing or empty: {target}")
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** (attempt - 1))
    return False


def download_folder(
    synapse: synapseclient.Synapse,
    token: str,
    folder_id: str,
) -> int:
    print("Listing Synapse files...", flush=True)
    downloads = collect_downloads(synapse, folder_id)
    print(
        f"Queued {len(downloads):,} files with {DOWNLOAD_WORKERS} parallel workers",
        flush=True,
    )
    if not downloads:
        return 0

    completed = 0
    processed = 0
    failures: list[str] = []
    worker_count = min(DOWNLOAD_WORKERS, len(downloads))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(download_file, token, entity_id, parent_path, target): target
            for entity_id, parent_path, target in downloads
        }
        for future in as_completed(futures):
            target = futures[future]
            processed += 1
            try:
                if future.result():
                    completed += 1
            except Exception as error:
                failures.append(f"{target}: {error}")

            if processed % 100 == 0 or processed == len(downloads):
                print(
                    f"Processed {processed:,}/{len(downloads):,}; "
                    f"downloaded {completed:,}; failed {len(failures):,}",
                    flush=True,
                )

    if failures:
        failure_log = DESTINATION / "download_failures.txt"
        failure_log.write_text("\n".join(failures), encoding="utf-8")
        raise RuntimeError(
            f"{len(failures):,} downloads failed after retries. "
            f"See {failure_log} and rerun the command to resume."
        )

    return completed


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    token = os.getenv("SYNAPSE_AUTH_TOKEN") or os.getenv("SYNAPSE_TOKEN")
    if not token:
        raise RuntimeError(
            "Set SYNAPSE_AUTH_TOKEN to a Synapse Personal Access Token after "
            "accepting the CODA-TB data-use terms."
        )

    synapse = create_client(token, silent=False)
    deploy_directory = Path(__file__).resolve().parent.parent
    for name in LOCAL_METADATA_FILES:
        source = deploy_directory / name
        if not source.exists():
            raise FileNotFoundError(f"Missing local metadata file: {source}")
        shutil.copy2(source, DESTINATION / name)

    print(f"Downloading solicited metadata to {DESTINATION}", flush=True)
    synapse.get(SOLICITED_METADATA_ID, downloadLocation=str(DESTINATION))

    print(f"Downloading solicited WAV folder to {DESTINATION}", flush=True)
    downloaded = download_folder(synapse, token, SOLICITED_FOLDER_ID)
    print(
        f"CODA-TB solicited download complete; {downloaded:,} new files",
        flush=True,
    )


if __name__ == "__main__":
    main()
