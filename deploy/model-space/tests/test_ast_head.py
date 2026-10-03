"""Fast CPU-only synthetic checks; no audio, downloads, or dataset training."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from tests.factories import build_metadata
from training import ast_head as head
from training.dataset import PatientExample
from training.encoding import CLINICAL_FEATURE_ORDER, ClinicalPreprocessor


@pytest.fixture(autouse=True)
def single_threaded_cpu():
    previous_threads, previous_rng = torch.get_num_threads(), torch.get_rng_state()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous_threads)
    torch.set_rng_state(previous_rng)


def separable_data():
    labels = np.array([0, 1] * 8)
    features = np.repeat((2 * labels - 1)[:, None], 768, axis=1).astype(np.float32)
    features[:, -1] = 7.0
    return features, labels


def test_fit_train_only_scaler_learns_and_roundtrips_safely(tmp_path, capsys):
    train, labels = separable_data()
    validation = train.copy()
    validation[:, -1] = 9.0
    checkpoint = head.fit_head(train, labels, validation, labels, epochs=5, device="cpu")
    np.testing.assert_allclose(checkpoint["mean"], train.mean(axis=0))
    np.testing.assert_allclose(checkpoint["scale"], np.maximum(train.std(axis=0), 1e-6))
    assert checkpoint["mean"][-1] == 7 and checkpoint["scale"][-1] == pytest.approx(1e-6)
    assert checkpoint["input_dim"] == 768 and checkpoint["l2"] == 0.01
    assert 1 <= checkpoint["selected_epoch"] <= 5
    assert all(value.device.type == "cpu" and not value.requires_grad
               for value in checkpoint.values() if isinstance(value, torch.Tensor))
    probabilities = head.predict_head(checkpoint, train)
    assert probabilities.shape == (16,) and np.isfinite(probabilities).all()
    assert np.array_equal(probabilities >= 0.5, labels.astype(bool))
    path = tmp_path / "head.pt"
    torch.save(checkpoint, path)
    restored = torch.load(path, weights_only=True, map_location="cpu")
    np.testing.assert_array_equal(head.predict_head(restored, train), probabilities)
    expected = torch.sigmoid(torch.nn.functional.linear(
        (torch.tensor(validation) - checkpoint["mean"]) / checkpoint["scale"],
        checkpoint["weight"], checkpoint["bias"],
    )).squeeze(1).numpy()
    np.testing.assert_allclose(head.predict_head(restored, validation), expected)
    assert "epoch=5/5" in capsys.readouterr().out


@pytest.mark.parametrize("aucs,selected_epoch", [([0.5] * 5, 5), ([0.6, 0.9, 0.8, 0.7, 0.6], 2)])
def test_fit_matches_unweighted_bce_sum_l2_and_restores_selected_epoch(monkeypatch, aucs, selected_epoch):
    train = np.zeros((4, 3), dtype=np.float32)
    labels = np.array([0, 0, 0, 1], dtype=np.float32)
    torch.manual_seed(42)
    model = torch.nn.Linear(3, 1)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    criterion = torch.nn.BCEWithLogitsLoss()
    states = []
    for _ in range(5):
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(torch.tensor(train)).squeeze(1), torch.tensor(labels))
        (loss + 0.1 * model.weight.square().sum()).backward()
        optimizer.step()
        states.append(copy.deepcopy(model.state_dict()))
    scores = iter(aucs)
    monkeypatch.setattr(head, "roc_auc_score", lambda *args: next(scores))
    checkpoint = head.fit_head(train, labels, train, labels, epochs=5, l2=0.1, device="cpu")
    assert checkpoint["selected_epoch"] == selected_epoch
    torch.testing.assert_close(checkpoint["weight"], states[selected_epoch - 1]["weight"])
    torch.testing.assert_close(checkpoint["bias"], states[selected_epoch - 1]["bias"])


def test_fit_is_seeded_and_logs_tenth_and_final_epochs(capsys, monkeypatch):
    features, labels = separable_data()
    calls = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: calls.append((args, kwargs)))
    first = head.fit_head(features, labels, features, labels, epochs=11, device="cpu", log_prefix="probe")
    second = head.fit_head(features, labels, features, labels, epochs=11, device="cpu", log_prefix="probe")
    torch.testing.assert_close(first["weight"], second["weight"], rtol=0, atol=0)
    torch.testing.assert_close(first["bias"], second["bias"], rtol=0, atol=0)
    assert len(calls) == 4 and all(kwargs["flush"] is True for _, kwargs in calls)
    assert "probe epoch=10/11" in calls[0][0][0] and "epoch=11/11" in calls[1][0][0]
    assert "loss=" in calls[0][0][0] and "val_auc=" in calls[0][0][0]


@pytest.mark.parametrize("argument,value,message", [
    ("train_x", [1, 2], "shape"), ("validation_x", np.zeros((2, 3)), "dimensions"),
    ("train_x", np.empty((0, 2)), "shape"), ("train_x", [[0, np.nan], [1, 2]], "finite"),
    ("validation_x", [[0, np.inf], [1, 2]], "finite"),
    ("train_y", [0, 0], "both classes"), ("validation_y", [1, 1], "both classes"),
    ("validation_y", [0, 2], "binary"), ("train_y", [[0], [1]], "shape"),
    ("validation_y", [0, np.nan], "finite"), ("train_x", [["x", "y"]], "numeric"),
    ("epochs", 0, "epochs"), ("epochs", 1.5, "epochs"),
    ("l2", -0.1, "l2"), ("l2", float("inf"), "l2"), ("seed", -1, "seed"),
])
def test_fit_rejects_invalid_inputs(argument, value, message):
    arguments = dict(train_x=np.eye(2), train_y=[0, 1], validation_x=np.eye(2),
                     validation_y=[0, 1], epochs=1, device="cpu")
    arguments[argument] = value
    with pytest.raises(ValueError, match=message):
        head.fit_head(**arguments)


@pytest.mark.parametrize("problem,message", [
    ("rank", "shape"), ("dimension", "dimension"), ("empty", "shape"), ("nan", "finite"),
    ("weight", "shape"), ("missing", "missing bias"), ("scale", "scale"),
    ("bias", "finite"), ("overflow", "logits"),
])
def test_predict_validates_inputs_and_checkpoint(problem, message):
    checkpoint = dict(mean=torch.zeros(2), scale=torch.ones(2), weight=torch.ones(1, 2),
                      bias=torch.zeros(1), input_dim=2)
    features = np.ones((2, 2), dtype=np.float32)
    if problem == "rank":
        features = features[0]
    elif problem == "dimension":
        features = features[:, :1]
    elif problem == "empty":
        features = features[:0]
    elif problem == "nan":
        features[0, 0] = np.nan
    elif problem == "weight":
        checkpoint["weight"] = torch.ones(2)
    elif problem == "missing":
        del checkpoint["bias"]
    elif problem == "scale":
        checkpoint["scale"][0] = 0
    elif problem == "bias":
        checkpoint["bias"][0] = float("inf")
    else:
        checkpoint["weight"][:] = 3e38
    with pytest.raises(ValueError, match=message):
        head.predict_head(checkpoint, features)


def test_cuda_never_silently_falls_back(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA"):
        head.fit_head(np.eye(2), [0, 1], np.eye(2), [0, 1], epochs=1)


@pytest.fixture
def cohort():
    examples = [PatientExample(f"synthetic-{i}", i % 2, (Path(f"clip-{i}.wav"),),
                               build_metadata(age=20 + 10 * i, Country="PH")) for i in range(6)]
    partitions = [
        {"fold": 0, "train": [4, 5], "validation": [2, 3], "test": [0, 1]},
        {"fold": 1, "train": [0, 1], "validation": [4, 5], "test": [2, 3]},
        {"fold": 2, "train": [2, 3], "validation": [0, 1], "test": [4, 5]},
    ]
    embeddings = np.repeat(np.arange(6)[:, None], 768, axis=1).astype(np.float32)
    return examples, embeddings, partitions


def test_benchmark_grid_train_only_preprocessing_thresholds_and_safe_reports(cohort, tmp_path, monkeypatch):
    examples, embeddings, partitions = cohort
    fits, predicted, fitted_rows = [], [], []
    original_preprocessor_fit = ClinicalPreprocessor.fit
    probability_table = np.array([0.6, 0.7, 0.2, 0.8, 0.1, 0.4])

    def fit_preprocessor(cls, rows):
        fitted_rows.append(rows)
        return original_preprocessor_fit(rows)

    def fit(train_x, train_y, validation_x, validation_y, **options):
        fold = options["seed"] - 42
        partition = partitions[fold]
        preprocessor = original_preprocessor_fit([examples[i].metadata for i in partition["train"]])
        clinical = np.stack([preprocessor.transform(e.metadata, cough_count=1) for e in examples])
        expected = {768: embeddings, 27: clinical, 795: np.concatenate((embeddings, clinical), axis=1)}
        all_features = expected[train_x.shape[1]]
        np.testing.assert_array_equal(train_x, all_features[partition["train"]])
        np.testing.assert_array_equal(validation_x, all_features[partition["validation"]])
        np.testing.assert_array_equal(train_y, [examples[i].label for i in partition["train"]])
        np.testing.assert_array_equal(validation_y, [examples[i].label for i in partition["validation"]])
        fits.append((fold, train_x.shape[1], options["l2"]))
        dimension = train_x.shape[1]
        return dict(mean=torch.tensor(train_x.mean(0)), scale=torch.ones(dimension),
                    weight=torch.zeros(1, dimension), bias=torch.zeros(1), input_dim=dimension,
                    selected_epoch=2, l2=options["l2"], validation_auc=0.5 if options["l2"] == 0.001 else 0.9,
                    validation_bce=1 / options["l2"], synthetic_fold=fold)

    def predict(state, features, **options):
        fold = state["synthetic_fold"]
        assert state["l2"] == 0.01  # .1 ties AUROC and has lower BCE, which must be ignored here.
        split = "validation" if len(predicted) % 2 == 0 else "test"
        indices = partitions[fold][split]
        assert len(features) == len(indices)
        predicted.append((fold, split))
        return probability_table[indices]

    monkeypatch.setattr(ClinicalPreprocessor, "fit", classmethod(fit_preprocessor))
    monkeypatch.setattr(head, "fit_head", fit)
    monkeypatch.setattr(head, "predict_head", predict)
    reports = head.benchmark_heads(examples, embeddings, partitions, tmp_path, epochs=2, device="cpu")
    json.dumps(reports, allow_nan=False)
    assert fitted_rows == [[examples[i].metadata for i in p["train"]] for p in partitions]
    assert len(fits) == 27 and len(predicted) == 18
    assert set(fits) == {(f, d, l2) for f in range(3) for d in (768, 27, 795) for l2 in head.L2_GRID}
    assert set(reports) == {"ast_audio", "clinical_only", "ast_clinical"}
    for mode, report in reports.items():
        assert report["oof"]["indices"] == list(range(6))
        assert report["oof"]["folds"] == [0, 0, 1, 1, 2, 2]
        assert report["oof"]["labels"] == [0, 1, 0, 1, 0, 1]
        assert report["oof"]["probabilities"] == probability_table.tolist()
        assert report["oof"]["thresholds"] == [0.8, 0.8, 0.4, 0.4, 0.7, 0.7]
        assert report["oof"]["predictions"] == [False, False, False, True, False, False]
        assert report["pooled_metrics"]["sensitivity"] == pytest.approx(1 / 3)
        assert report["pooled_metrics"]["specificity"] == 1
        for fold_report in report["folds"]:
            assert fold_report["selected_l2"] == 0.01 and fold_report["selected_epoch"] == 2
            path = Path(fold_report["checkpoint_path"])
            assert path == tmp_path / mode / f"fold-{fold_report['fold']}" / "head.pt"
            state = torch.load(path, weights_only=True, map_location="cpu")
            assert state["architecture"] == "frozen_ast_linear_v1" and state["input_mode"] == mode
            assert state["clinical_preprocessor"] == fold_report["clinical_preprocessor"]
            assert state["clinical_preprocessor"]["clinical_feature_order"] == list(CLINICAL_FEATURE_ORDER)
            assert json.loads(path.with_name("report.json").read_text()) == fold_report


def test_benchmark_real_cpu_smoke_exports_nine_heads(cohort, tmp_path):
    examples, embeddings, partitions = cohort
    reports = head.benchmark_heads(examples, embeddings, partitions, tmp_path, epochs=1, device="cpu")
    assert len(list(tmp_path.rglob("head.pt"))) == 9
    json.dumps(reports, allow_nan=False)
    for mode, dimension in (("ast_audio", 768), ("clinical_only", 27), ("ast_clinical", 795)):
        assert reports[mode]["param_count"] == dimension + 1
        assert reports[mode]["pooled_metrics"]["sample_count"] == 6
        for fold_report in reports[mode]["folds"]:
            state = torch.load(fold_report["checkpoint_path"], weights_only=True, map_location="cpu")
            assert state["input_dim"] == dimension
            assert state["selected_epoch"] == 1
            assert state["validation_auc"] == fold_report["validation_auc"]
            assert np.isfinite(head.predict_head(state, np.zeros((1, dimension)))).all()


@pytest.mark.parametrize("problem,message", [
    ("overlap", "disjoint"), ("missing", "exactly one"), ("repeated", "exactly one"),
    ("single_class", "both classes"), ("dimension", "shape"), ("nan", "finite"),
])
def test_benchmark_fails_before_training_for_invalid_cohorts(cohort, tmp_path, monkeypatch, problem, message):
    examples, embeddings, partitions = cohort
    if problem == "overlap":
        partitions[0]["train"].append(0)
    elif problem == "missing":
        partitions.pop()
    elif problem == "repeated":
        partitions.append({**partitions[0], "fold": 3})
    elif problem == "single_class":
        partitions[0]["validation"] = [2]
    elif problem == "dimension":
        embeddings = embeddings[:, :10]
    else:
        embeddings[0, 0] = np.nan
    monkeypatch.setattr(head, "fit_head", lambda *args, **kwargs: pytest.fail("must validate before fitting"))
    with pytest.raises(ValueError, match=message):
        head.benchmark_heads(examples, embeddings, partitions, tmp_path, device="cpu")
    assert not list(tmp_path.iterdir())


def test_refit_fixed_epochs_matches_objective_and_roundtrips_without_evaluation(tmp_path, monkeypatch):
    features = np.array([[1, 4, 9], [2, 2, 9], [3, 6, 9], [8, -2, 9]], dtype=np.float32)
    labels = np.array([0, 0, 0, 1], dtype=np.float32)
    mean = torch.tensor(features).double().mean(0).float()
    scale = torch.tensor(features).double().std(0, correction=0).clamp_min(1e-6).float()
    normalized = ((torch.tensor(features).double() - mean) / scale).float()
    torch.manual_seed(17)
    reference = torch.nn.Linear(3, 1)
    optimizer = torch.optim.Adam(reference.parameters(), lr=0.01)
    criterion = torch.nn.BCEWithLogitsLoss()
    for _ in range(5):
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(reference(normalized).squeeze(1), torch.tensor(labels))
        (loss + 0.1 * reference.weight.square().sum()).backward()
        optimizer.step()
    for name in ("fit_head", "roc_auc_score", "_metrics", "_validation_threshold"):
        monkeypatch.setattr(head, name, lambda *a, **kw: pytest.fail("refit must not select or evaluate"))
    state = head.refit_head(features, labels, epochs=5, l2=0.1, seed=17, device="cpu")
    assert set(state) == {"mean", "scale", "weight", "bias", "input_dim", "l2", "selected_epoch",
                          "architecture", "fit_strategy"}
    assert state["selected_epoch"] == 5 and state["l2"] == 0.1 and state["input_dim"] == 3
    assert state["fit_strategy"] == "fixed_epochs_full_development_cohort"
    assert state["architecture"] == "frozen_ast_linear_v1"
    torch.testing.assert_close(state["mean"], mean, rtol=0, atol=0)
    torch.testing.assert_close(state["scale"], scale, rtol=0, atol=0)
    assert state["scale"][-1] == pytest.approx(1e-6)
    for name, expected in reference.state_dict().items():
        torch.testing.assert_close(state[name], expected, rtol=0, atol=0)
    assert all(t.device.type == "cpu" and not t.requires_grad and torch.isfinite(t).all()
               for t in state.values() if isinstance(t, torch.Tensor))
    path = tmp_path / "refit.pt"
    torch.save(state, path)
    restored = torch.load(path, weights_only=True, map_location="cpu")
    np.testing.assert_array_equal(head.predict_head(restored, features), head.predict_head(state, features))
    np.testing.assert_allclose(head.predict_head(restored, features),
                               reference(normalized).sigmoid().detach().numpy().ravel(), rtol=1e-6)


def test_refit_is_seeded_and_logs_only_training_loss_every_ten_and_final(monkeypatch):
    calls = []
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: calls.append((args, kwargs)))
    features, labels = separable_data()
    first = head.refit_head(features, labels, epochs=11, l2=0.01, device="cpu")
    second = head.refit_head(features, labels, epochs=11, l2=0.01, device="cpu")
    torch.testing.assert_close(first["weight"], second["weight"], rtol=0, atol=0)
    torch.testing.assert_close(first["bias"], second["bias"], rtol=0, atol=0)
    assert len(calls) == 4 and all(options["flush"] is True for _, options in calls)
    assert "epoch=10/11" in calls[0][0][0] and "epoch=11/11" in calls[1][0][0]
    assert all("loss=" in args[0] and "val" not in args[0] and "auc" not in args[0] for args, _ in calls)


@pytest.mark.parametrize("argument,value,message", [
    ("train_x", [1, 2], "shape"), ("train_x", np.empty((0, 2)), "shape"),
    ("train_x", [[0, np.nan], [1, 2]], "finite"), ("train_y", [0, 0], "both classes"),
    ("train_y", [0, 2], "binary"), ("train_y", [[0], [1]], "shape"),
    ("train_y", [0, np.inf], "finite"), ("epochs", 0, "epochs"), ("epochs", 1.5, "epochs"),
    ("l2", -0.1, "l2"), ("l2", float("nan"), "l2"), ("seed", -1, "seed"),
])
def test_refit_reuses_training_input_guards(argument, value, message):
    arguments = dict(train_x=np.eye(2), train_y=[0, 1], epochs=1, l2=0.01, device="cpu")
    arguments[argument] = value
    with pytest.raises(ValueError, match=message):
        head.refit_head(**arguments)
