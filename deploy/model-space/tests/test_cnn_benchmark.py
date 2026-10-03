"""Fast CPU contract checks; training and audio extraction are mocked."""

from __future__ import annotations

import copy
import inspect
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from src.audio_features import AudioFeatureConfig
from training import cnn_benchmark as benchmark
from training import cross_validate_fusion as fusion
from training.dataset import PatientExample, _spread_sample
from training.encoding import CLINICAL_FEATURE_ORDER, NUMERIC_FIELDS, ClinicalPreprocessor


@pytest.fixture
def examples():
    return [
        PatientExample(
            f"private-subject-{i}", i % 2,
            tuple(Path(f"subject-{i}-clip-{j}.wav") for j in range(10 if i == 0 else 2)),
            {**dict.fromkeys(NUMERIC_FIELDS, 10.0), "age": float(20 + i * 10),
             "Country": "PH", "HIVstatus": "Unknown"},
        )
        for i in range(6)
    ]


@pytest.fixture
def partitions():
    return [
        {"fold": 0, "train": [4, 5], "validation": [2, 3], "test": [0, 1]},
        {"fold": 1, "train": [0, 1], "validation": [4, 5], "test": [2, 3]},
        {"fold": 2, "train": [2, 3], "validation": [0, 1], "test": [4, 5]},
    ]


def test_threshold_and_metrics_handle_ties():
    labels = np.array([0, 1, 0, 1])
    probabilities = np.full(4, 0.5)
    threshold = benchmark._validation_threshold(labels, probabilities)
    assert threshold == 0.5
    metrics = benchmark._metrics(labels, probabilities, probabilities >= threshold)
    assert metrics == {
        "auroc": 0.5, "average_precision": 0.5, "brier_score": 0.25,
        "sensitivity": 1.0, "specificity": 0.0,
        "sample_count": 4, "positive_count": 2, "negative_count": 2,
    }


def test_threshold_is_largest_meeting_ninety_percent():
    labels = np.array([0] + [1] * 10)
    probabilities = np.array([0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0])
    assert benchmark._validation_threshold(labels, probabilities) == 0.1


def test_threshold_ignores_infinite_candidates(monkeypatch):
    monkeypatch.setattr(benchmark, "roc_curve", lambda *args, **kwargs: (
        np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.9, 1.0]),
        np.array([np.inf, 0.8, 0.3]),
    ))
    assert benchmark._validation_threshold(np.array([0, 1]), np.array([0.3, 0.8])) == 0.8


@pytest.mark.parametrize("split", benchmark.SPLITS)
def test_rejects_single_class_splits(examples, partitions, split):
    partitions[0][split] = partitions[0][split][:1]
    with pytest.raises(ValueError, match="both classes"):
        benchmark._validate_partitions(examples, partitions)


def test_rejects_duplicate_patient_ids_without_disclosure(examples, partitions):
    examples[1] = replace(examples[1], patient_id=examples[0].patient_id)
    with pytest.raises(ValueError, match="unique") as error:
        benchmark._validate_partitions(examples, partitions)
    assert all(example.patient_id not in str(error.value) for example in examples)


@pytest.mark.parametrize("problem, message", [
    ("overlap", "disjoint"), ("duplicate_index", "duplicate subjects"),
    ("negative_index", "in-range"), ("bad_index", "in-range"),
    ("missing_test", "exactly one"), ("repeated_test", "exactly one"),
    ("duplicate_fold", "fold numbers must be unique"),
])
def test_partition_guards(examples, partitions, problem, message):
    if problem == "overlap":
        partitions[0]["train"].append(partitions[0]["test"][0])
    elif problem == "duplicate_index":
        partitions[0]["train"].append(partitions[0]["train"][0])
    elif problem == "negative_index":
        partitions[0]["train"][0] = -1
    elif problem == "bad_index":
        partitions[0]["train"][0] = len(examples)
    elif problem == "missing_test":
        partitions.pop()
    elif problem == "repeated_test":
        partitions.append({**copy.deepcopy(partitions[0]), "fold": 3})
    else:
        partitions[1]["fold"] = partitions[0]["fold"]
    with pytest.raises(ValueError, match=message):
        benchmark._validate_partitions(examples, partitions)


class TinyFusion(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(2, 3))
        self.register_buffer("not_a_parameter", torch.zeros(11))

    def forward(self, clips, metadata, clip_mask=None):
        score = metadata[:, 0] * self.weight[0, 0]
        return torch.stack((-score, score), dim=1)


def test_real_predict_tuple_contract_on_cpu(monkeypatch):
    monkeypatch.setattr(fusion, "_new_fusion_model", lambda *args: TinyFusion())
    config = AudioFeatureConfig()
    patients = tuple(fusion.FusionPatient(
        f"private-{i}", i, np.zeros((1, 1, config.n_mels, config.target_frames), np.float32),
        np.array([float(i)], np.float32),
    ) for i in range(2))
    labels, probabilities = benchmark._checked_predict(
        TinyFusion().state_dict(), patients, batch_size=2, audio_config=config,
        device=torch.device("cpu"), architecture=benchmark.ARCHITECTURES[0],
    )
    assert labels.tolist() == [0, 1]
    assert probabilities.tolist() == pytest.approx([0.5, 0.880797], abs=1e-6)


def test_benchmark_reuses_audio_and_locks_validation_thresholds(
    examples, partitions, tmp_path, monkeypatch, capsys,
):
    sources = []
    for example in examples:
        paths = tuple(tmp_path / path for path in example.audio_paths)
        for path in paths:
            path.write_bytes(path.name.encode())
        sources.append(replace(example, audio_paths=paths))
    extracted, fitted_rows, fits, predictions = [], [], [], []
    original_fit = ClinicalPreprocessor.fit

    def fit_preprocessor(cls, rows):
        fitted_rows.append(rows)
        return original_fit(rows)

    def extract(data, config):
        assert config == AudioFeatureConfig()
        extracted.append(data)
        return np.zeros((1, config.n_mels, config.target_frames), np.float32)

    def fit(train, validation, **kwargs):
        inspect.signature(fusion._fit).bind(train, validation, **kwargs)
        assert kwargs["spec_augment_enabled"] is False
        assert kwargs["distillation_weight"] == 0.0
        assert kwargs["false_negative_penalty"] == 1.0
        assert kwargs["device"] == torch.device("cpu")
        assert all(patient.teacher_logits is None for patient in (*train, *validation))
        assert all(len(patient.clips) <= 8 for patient in (*train, *validation))
        fits.append((train, validation, kwargs))
        return TinyFusion().state_dict(), 3

    probabilities = [0.6, 0.7, 0.2, 0.8, 0.1, 0.4]

    def predict(state, patients, **kwargs):
        inspect.signature(fusion._predict).bind(state, patients, **kwargs)
        assert all(value.device.type == "cpu" for value in state.values())
        predictions.append((patients, kwargs))
        indices = [int(patient.patient_id.rsplit("-", 1)[1]) for patient in patients]
        return tuple(patient.label for patient in patients), tuple(probabilities[i] for i in indices)

    monkeypatch.setattr(ClinicalPreprocessor, "fit", classmethod(fit_preprocessor))
    monkeypatch.setattr(fusion, "extract_log_mel", extract)
    monkeypatch.setattr(benchmark, "_fit", fit)
    monkeypatch.setattr(benchmark, "_predict", predict)
    monkeypatch.setattr(benchmark, "_new_fusion_model", lambda *args: TinyFusion())
    report = benchmark.benchmark_cnns(
        sources, partitions, tmp_path / "weights", epochs=4, batch_size=2, seed=42, device="cpu",
    )
    json.dumps(report, allow_nan=False)
    assert set(report) == set(benchmark.ARCHITECTURES)
    assert len(fits) == 6 and len(predictions) == 12
    assert extracted == list(dict.fromkeys(extracted))
    assert set(extracted) == {
        path.name.encode() for example in sources for path in _spread_sample(example.audio_paths, 8)
    }
    assert fitted_rows == [[sources[i].metadata for i in p["train"]] for p in partitions]
    age_index = CLINICAL_FEATURE_ORDER.index("age")
    for fold, partition in enumerate(partitions):
        left, right = fits[2 * fold:2 * fold + 2]
        assert left[0] is right[0] and left[1] is right[1]
        assert left[2]["seed"] == right[2]["seed"] == 42 + fold
        assert [left[2]["architecture"], right[2]["architecture"]] == list(benchmark.ARCHITECTURES)
        assert [patient.clinical[age_index] for patient in left[0]] == pytest.approx([-1, 1])
    checkpoints = []
    for model_report in report.values():
        assert model_report["param_count"] == 6  # Excludes the 11-element state buffer.
        assert model_report["oof"]["probabilities"] == probabilities
        assert model_report["oof"]["predictions"] == [False, False, False, True, False, False]
        assert model_report["oof"]["thresholds"] == [0.8, 0.8, 0.4, 0.4, 0.7, 0.7]
        assert model_report["pooled_metrics"]["sensitivity"] == pytest.approx(1 / 3)
        assert model_report["pooled_metrics"]["specificity"] == 1.0
        for fold in model_report["folds"]:
            assert fold["selected_epoch"] == 3 and fold["validation_auc"] == 1.0
            checkpoint = Path(fold["checkpoint_path"])
            state = torch.load(checkpoint, map_location="cpu", weights_only=True)
            assert all(value.device.type == "cpu" for value in state.values())
            checkpoints.append(checkpoint)
    assert len(set(checkpoints)) == 6
    logs = capsys.readouterr().out
    assert all(example.patient_id not in logs for example in sources)
    assert all(f"model={name} fold={fold}" in logs for name in benchmark.ARCHITECTURES for fold in range(3))
