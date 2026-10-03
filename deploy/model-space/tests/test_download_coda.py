"""CODA TB downloader, exercised without touching Synapse.

The real download needs an account, 395 GB of traffic and a signed data-use
agreement, so the point of these tests is that the logic around that call is
right: the wanted-file set, the path mapping, and the failure messages an
operator will actually read.
"""

from __future__ import annotations

import csv

import pytest

import download_coda


def _write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _metadata(destination):
    _write_csv(destination / "clinical.csv", [{"participant": "P1"}], ["participant"])
    _write_csv(destination / "additional.csv", [{"participant": "P1"}], ["participant"])
    _write_csv(
        destination / "solicited.csv",
        [
            {"participant": "P1", "filename": "P1_c1.wav"},
            {"participant": "P1", "filename": "P1_c2.wav"},
            {"participant": "P2", "filename": "P2_c1.wav"},
        ],
        ["participant", "filename"],
    )
    return destination


# ── wanted filenames ────────────────────────────────────────────────────────


def test_wanted_filenames_come_from_solicited_csv(tmp_path) -> None:
    _metadata(tmp_path)
    assert download_coda._wanted_filenames(tmp_path, include_longitudinal=False) == {
        "P1_c1.wav",
        "P1_c2.wav",
        "P2_c1.wav",
    }


def test_visit_control_is_excluded_unless_requested(tmp_path) -> None:
    """Visit-control visits are the longitudinal subset. Pulling them by
    default multiplies the same participants' recordings, which inflates clip
    counts without adding independent subjects."""
    _metadata(tmp_path)
    _write_csv(
        tmp_path / "visit_control.csv",
        [{"participant": "P1", "filename": "P1_visit2.wav"}],
        ["participant", "filename"],
    )
    assert "P1_visit2.wav" not in download_coda._wanted_filenames(
        tmp_path, include_longitudinal=False
    )
    assert "P1_visit2.wav" in download_coda._wanted_filenames(
        tmp_path, include_longitudinal=True
    )


def test_wanted_filenames_ignore_blank_entries(tmp_path) -> None:
    _write_csv(
        tmp_path / "solicited.csv",
        [{"participant": "P1", "filename": ""}, {"participant": "P1", "filename": "real.wav"}],
        ["participant", "filename"],
    )
    assert download_coda._wanted_filenames(tmp_path, include_longitudinal=False) == {"real.wav"}


def test_wanted_filenames_require_a_filename_column(tmp_path) -> None:
    _write_csv(tmp_path / "solicited.csv", [{"participant": "P1"}], ["participant"])
    with pytest.raises(SystemExit) as raised:
        download_coda._wanted_filenames(tmp_path, include_longitudinal=False)
    assert raised.value.code == 1


def test_missing_metadata_is_a_loud_failure_not_a_silent_empty_set(tmp_path) -> None:
    """Silently downloading nothing wastes 395 GB of the operator's time."""
    with pytest.raises(SystemExit):
        download_coda._wanted_filenames(tmp_path, include_longitudinal=False)


# ── metadata download ───────────────────────────────────────────────────────


class _FakeClient:
    """Mimics synapseclient.Synapse.get for a metadata bundle."""

    def __init__(self, provided: set[str]):
        self.provided = provided
        self.requested: list[str] = []

    def get(self, entity, downloadLocation=None):
        import pathlib

        self.requested.append(entity)
        if entity not in self.provided:
            raise RuntimeError(f"404 {entity}")
        destination = pathlib.Path(downloadLocation)
        destination.mkdir(parents=True, exist_ok=True)
        for name in download_coda.METADATA_FILENAMES:
            (destination / name).write_text("participant,filename\n", encoding="utf-8")


def test_download_metadata_fetches_from_the_published_entity(tmp_path) -> None:
    client = _FakeClient({download_coda.SYNAPSE_METADATA_ID})
    destination = download_coda.download_metadata(client, tmp_path / "coda")
    assert client.requested == [download_coda.SYNAPSE_METADATA_ID]
    for name in download_coda.METADATA_FILENAMES:
        assert (destination / name).is_file(), name


class _PartialClient(_FakeClient):
    """Downloads succeed, but Synapse only offers two of the three tables.

    This is what a silent upstream rename looks like from here, and it must
    not be mistaken for a cohort with no participants.
    """

    def get(self, entity, downloadLocation=None):
        import pathlib

        destination = pathlib.Path(downloadLocation)
        destination.mkdir(parents=True, exist_ok=True)
        for name in download_coda.METADATA_FILENAMES[:2]:
            (destination / name).write_text("participant,filename\n", encoding="utf-8")


def test_download_metadata_fails_loudly_when_the_layout_changes(tmp_path, capsys) -> None:
    """A renamed Synapse file must not be mistaken for an empty download, and
    must not reach the training loader as a silent no-op."""
    client = _PartialClient({download_coda.SYNAPSE_METADATA_ID})
    with pytest.raises(SystemExit) as raised:
        download_coda.download_metadata(client, tmp_path / "coda")
    assert raised.value.code == 1
    error = capsys.readouterr().err
    assert "solicited.csv" in error
    assert "layout may have changed" in error


def test_download_metadata_reports_a_transport_failure(tmp_path, capsys) -> None:
    client = _FakeClient(set())
    with pytest.raises(SystemExit):
        download_coda.download_metadata(client, tmp_path / "coda")
    assert download_coda.SYNAPSE_METADATA_ID in capsys.readouterr().err


# ── remote listing ──────────────────────────────────────────────────────────
#
# The shapes below are copied from synapseclient 4.14.0 against the real
# syn40358494: getChildren returns plain dicts whose type key is
# "org.sagebionetworks.repo.model.FileEntity", and names are
# "<epoch_ms>-recording-<n>.wav". An earlier version of this file read fields
# with getattr only, which returned None for dicts and made the downloader
# report success while fetching nothing.


class _FakeRemote:
    def __init__(self, name, identifier, kind):
        self.name = name
        self.id = identifier
        self.type = kind
        self.concreteType = None


class _DictRemote(dict):
    """The real synapseclient 4.x child: a plain dict."""


class _FakeSynapse:
    def __init__(self, children):
        self.children = children

    def getChildren(self, parent):
        return self.children


def _real_dict(name, identifier, kind="org.sagebionetworks.repo.model.FileEntity"):
    return _DictRemote(
        {
            "id": identifier,
            "name": name,
            "type": kind,
            "isLatestVersion": True,
            "versionNumber": 1,
        }
    )


def test_remote_files_are_read_from_plain_dicts():
    """A getattr-only reader returns None for dicts and downloads nothing."""
    tree = _FakeSynapse([_real_dict("1620627399144-recording-1.wav", "syn40395744")])
    assert list(download_coda._iter_remote_files(tree, "syn40358494")) == [
        ("syn40395744", "1620627399144-recording-1.wav")
    ]


def test_real_folder_entities_are_descended_into():
    tree = _FakeSynapse(
        [
            _real_dict("visit_01", "syn100", "org.sagebionetworks.repo.model.FolderEntity"),
            _real_dict("1620627399144-recording-1.wav", "syn40395744"),
        ]
    )

    class _Nested(_FakeSynapse):
        def getChildren(self, parent):
            if parent == "syn40358494":
                return tree.children
            if parent == "syn100":
                return [_real_dict("1620627399144-recording-1.wav", "syn40395744")]
            return []

    found = list(download_coda._iter_remote_files(_Nested([]), "syn40358494"))
    assert ("syn40395744", "1620627399144-recording-1.wav") in found


def test_file_entities_are_never_treated_as_folders():
    """The type string contains 'FileEntity', which also matches a naive
    'entity' substring test."""
    assert not download_coda._is_folder_entity(
        _real_dict("a.wav", "syn1", "org.sagebionetworks.repo.model.FileEntity")
    )
    assert download_coda._is_folder_entity(
        _real_dict("v1", "syn2", "org.sagebionetworks.repo.model.FolderEntity")
    )


def test_attribute_style_children_still_work():
    """Older synapseclient releases return objects, and existing callers rely
    on both shapes."""
    tree = _FakeSynapse([_FakeRemote("P1_c1.wav", "syn300", "FILE")])
    assert list(download_coda._iter_remote_files(tree, "syn40358494")) == [
        ("syn300", "P1_c1.wav")
    ]


def test_iter_remote_files_returns_id_then_name():
    tree = _FakeSynapse([_FakeRemote("P1_c1.wav", "syn300", "FILE")])
    assert list(download_coda._iter_remote_files(tree, "syn40358494")) == [
        ("syn300", "P1_c1.wav")
    ]


def test_iter_remote_files_survives_an_unreadable_folder():
    class _Broken(_FakeSynapse):
        def getChildren(self, parent):
            if parent == "syn40358494":
                return [_FakeRemote("visit_01", "syn100", "FOLDER")]
            raise RuntimeError("permission denied")

    # Must warn, not abort the whole 395 GB pull.
    assert list(download_coda._iter_remote_files(_Broken([]), "syn40358494")) == []


# ── path mapping ────────────────────────────────────────────────────────────


def test_resolve_download_target_flattens_a_bare_filename(tmp_path) -> None:
    target = download_coda._resolve_download_target(None, "syn1", "P1_c1.wav", tmp_path)
    assert target == tmp_path / "P1_c1.wav"


def test_resolve_download_target_preserves_the_visit_subdirectory(tmp_path) -> None:
    """The loader joins paths against the audio root, so the remote layout has
    to be reproduced on disk or every file resolves to the wrong place."""
    target = download_coda._resolve_download_target(
        None, "syn1", "visit_01/P1_c1.wav", tmp_path
    )
    assert target == tmp_path / "visit_01" / "P1_c1.wav"


def test_resolve_download_target_cannot_escape_the_destination(tmp_path) -> None:
    """A remote name is untrusted input. Writing outside the destination would
    be a traversal, the same class the model loader already guards against."""
    for hostile in ("../../etc/passwd", "a/../../../evil.wav", "..\\..\\win.ini"):
        with pytest.raises(SystemExit):
            download_coda._resolve_download_target(None, "syn1", hostile, tmp_path)


def test_resolve_download_target_rejects_absolute_paths(tmp_path) -> None:
    for hostile in ("/etc/passwd", "C:/Windows/system32/evil.dll"):
        with pytest.raises(SystemExit):
            download_coda._resolve_download_target(None, "syn1", hostile, tmp_path)


def test_resolve_download_target_rejects_a_nameless_entity(tmp_path) -> None:
    with pytest.raises(SystemExit):
        download_coda._resolve_download_target(None, "syn1", "   ", tmp_path)


def test_resolve_download_target_stays_inside_for_normal_names(tmp_path) -> None:
    for name in ("P1_c1.wav", "visit_01/P1_c1.wav", "./visit_01//P1_c1.wav"):
        resolved = download_coda._resolve_download_target(None, "syn1", name, tmp_path).resolve()
        assert tmp_path.resolve() in resolved.parents, name


# ── participant cap ─────────────────────────────────────────────────────────


class _AudioClient(_FakeSynapse):
    """Fake Synapse that hands back audio entities and records each fetch."""

    def __init__(self, children):
        super().__init__(children)
        self.fetched: list[str] = []

    def get(self, identifier, downloadLocation=None):
        self.fetched.append(identifier)


def _audio_tree(*pairs):
    return [_FakeRemote(name, f"syn{index}", "FILE") for index, name in enumerate(pairs)]


def test_participant_cap_counts_participants_not_files(tmp_path, capsys) -> None:
    """CODA-TB participants contribute a very uneven number of clips. Capping
    the file count instead would admit far fewer than the requested people."""
    _write_csv(
        tmp_path / "solicited.csv",
        [{"participant": f"P{p}", "filename": f"P{p}_c{c}.wav"} for p in range(6) for c in range(5)],
        ["participant", "filename"],
    )
    tree = _AudioClient(
        _audio_tree(*[f"P{p}_c{c}.wav" for p in range(6) for c in range(5)])
    )
    download_coda.download_audio(
        tree, tmp_path, include_longitudinal=False, limit_participants=2, dry_run=False
    )
    error = capsys.readouterr().out
    assert "from 2 participants" in error
    assert "--limit-participants=2" in error


def test_dry_run_fetches_nothing(tmp_path, capsys) -> None:
    """A dry run exists so nobody discovers the size of the download the hard
    way; it must not move a single byte."""
    _metadata(tmp_path)
    tree = _AudioClient(_audio_tree("P1_c1.wav", "P1_c2.wav", "P2_c1.wav"))
    download_coda.download_audio(
        tree, tmp_path, include_longitudinal=False, limit_participants=None, dry_run=True
    )
    assert tree.fetched == []
    assert "would fetch" in capsys.readouterr().out


def test_download_audio_fails_when_nothing_matches(tmp_path, capsys) -> None:
    """An empty result means the remote layout changed, not that the dataset
    is unavailable; say which so the operator can go look."""
    _metadata(tmp_path)
    tree = _AudioClient(_audio_tree("something_else.wav"))
    with pytest.raises(SystemExit) as raised:
        download_coda.download_audio(
            tree, tmp_path, include_longitudinal=False, limit_participants=None, dry_run=False
        )
    assert raised.value.code == 1
    assert "layout may differ" in capsys.readouterr().err


def test_participant_cap_rejects_a_nonsense_limit(tmp_path) -> None:
    _metadata(tmp_path)
    with pytest.raises(SystemExit):
        download_coda.download_audio(
            _AudioClient([]),
            tmp_path,
            include_longitudinal=False,
            limit_participants=0,
            dry_run=False,
        )


def test_participant_lookup_prefers_the_metadata_mapping(tmp_path) -> None:
    _write_csv(
        tmp_path / "solicited.csv",
        [{"participant": "CODA-0007", "filename": "visit_01/0007_c1.wav"}],
        ["participant", "filename"],
    )
    assert (
        download_coda._participant_for_filename(tmp_path, "visit_01/0007_c1.wav")
        == "CODA-0007"
    )


def test_participant_lookup_returns_none_when_unknown(tmp_path) -> None:
    _write_csv(
        tmp_path / "solicited.csv",
        [{"participant": "CODA-0007", "filename": "a.wav"}],
        ["participant", "filename"],
    )
    assert download_coda._participant_for_filename(tmp_path, "b.wav") is None


# ── CLI surface ─────────────────────────────────────────────────────────────


def test_error_helper_returns_a_nonzero_exit_code():
    with pytest.raises(SystemExit) as raised:
        raise download_coda._fail("something went wrong")
    assert raised.value.code == 1


def test_missing_token_names_the_setup_steps(monkeypatch, capsys) -> None:
    """The Synapse application is a manual process; the message has to say so,
    or the operator burns an hour wondering whether it is a bug."""
    monkeypatch.delenv("SYNAPSE_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit) as raised:
        download_coda._login(object())
    assert raised.value.code == 1
    error = capsys.readouterr().err
    assert "SYNAPSE_AUTH_TOKEN" in error
    assert "Certified" in error and "syn50353157" in error


def test_module_declares_the_published_synapse_identifiers():
    assert download_coda.SYNAPSE_FOLDER_ID == "syn40358494"
    assert download_coda.SYNAPSE_METADATA_ID == "syn41604939"
    assert download_coda.METADATA_FILENAMES == (
        "clinical.csv",
        "additional.csv",
        "solicited.csv",
    )
