"""Guard the patient-level split and input/output contract of the benchmark CLI."""
import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from training.cnn_benchmark import _validate_partitions
from training.run_benchmark import _partitions, build_parser, run


def examples(count=60):
    return [SimpleNamespace(patient_id=f"subject-{index}", label=index % 2,
                            audio_paths=(Path(f"audio-{index}.wav"),), metadata={})
            for index in range(count)]


def test_partitions_are_reproducible_and_patient_disjoint():
    cohort = examples()
    actual = _partitions(cohort, 3, 42)
    assert actual == _partitions(cohort, 3, 42)
    _validate_partitions(cohort, actual)
    assert sorted(index for fold in actual for index in fold["test"]) == list(range(60))
    assert actual != _partitions(cohort, 3, 43)


def test_partitions_have_expected_outer_and_inner_counts():
    actual = _partitions(examples(), 3, 42)
    assert [(len(f["train"]), len(f["validation"]), len(f["test"])) for f in actual] == [(32, 8, 20)] * 3


def test_parser_requires_actual_dataset_paths():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_parser_uses_conservative_gpu_batch():
    arguments = ["--clinical-metadata", "clinical.csv", "--additional-metadata", "additional.csv",
                 "--solicited-metadata", "solicited.csv", "--audio-root", "audio",
                 "--output-dir", "output"]
    args = build_parser().parse_args(arguments)
    assert args.device == "cuda"
    assert args.ast_batch_size == 1
    assert args.folds == 3
    assert args.cnn_epochs == 8
    assert args.head_epochs == 120


@pytest.mark.parametrize("report", ["cnn-reports.json", "head-reports.json"])
def test_run_refuses_to_overwrite_completed_reports(tmp_path, report):
    saved = tmp_path / report
    saved.write_text("original", encoding="utf-8")
    args = argparse.Namespace(seed=42, output_dir=tmp_path)
    with pytest.raises(ValueError, match="already contains reports"):
        run(args)
    assert saved.read_text(encoding="utf-8") == "original"
