from __future__ import annotations

import pytest

from download_tb_screen import extracted_path


def test_extracted_path_removes_archive_root(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = extracted_path(
        "TBscreen_Dataset/Passive_coughs/Audio_files/PID_1.wav"
    )

    assert result.as_posix().endswith(
        "data/tbscreen/TBscreen_Dataset/Passive_coughs/Audio_files/PID_1.wav"
    )


def test_extracted_path_rejects_member_outside_dataset() -> None:
    with pytest.raises(ValueError, match="TBscreen_Dataset"):
        extracted_path("other/archive.wav")
