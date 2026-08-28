from __future__ import annotations

import os
from pathlib import Path


SYNAPSE_FOLDER_ID = "syn40358494"
SYNAPSE_METADATA_ID = "syn41604939"


def main() -> None:
    """Download CODA-TB only after the operator supplies a Synapse token."""
    token = os.getenv("SYNAPSE_AUTH_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "SYNAPSE_AUTH_TOKEN is required after accepting CODA-TB data-use terms."
        )
    try:
        import synapseclient
    except ImportError as error:
        raise SystemExit(
            "Install synapseclient separately in a data-download environment."
        ) from error

    destination = Path(os.getenv("CODA_DATA_DIR", "coda-tb")).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    client = synapseclient.Synapse(silent=False)
    client.login(authToken=token)
    client.get(SYNAPSE_METADATA_ID, downloadLocation=str(destination))
    client.getChildren(SYNAPSE_FOLDER_ID)
    print(
        "Metadata downloaded. Enumerate/download the permitted audio files using "
        "the Synapse terms and keep them outside version control."
    )


if __name__ == "__main__":
    main()
