"""Synthetic, CPU-only checks for aligned OOF aggregation and paired uncertainty."""

import copy
import json

import numpy as np
import pytest
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from training import benchmark_summary as summary


@pytest.fixture
def reports():
    labels = np.tile([0, 1, 0, 1], 3)
    folds = np.repeat(np.arange(3), 4)
    thresholds = np.repeat([0.5, 0.55, 0.3], 4)
    base = np.array([0.1, 0.6, 0.7, 0.5, 0.55, 0.55, 0.2, 0.8, 0.0, 1.0, 0.4, 0.3])
    result = {}
    for shift, name in enumerate(summary.MODELS):
        probabilities = np.roll(base, shift)
        result[name] = {
            "patient_ids": ["private-subject-do-not-export"], "pooled_metrics": {"auroc": -42},
            "oof": {"indices": list(range(12)), "folds": folds.tolist(), "labels": labels.tolist(),
                    "probabilities": probabilities.tolist(), "thresholds": thresholds.tolist(),
                    "predictions": (probabilities >= thresholds).tolist()},
            "folds": [{"fold": fold, "sample_count": 4, "positive_count": 2, "negative_count": 2,
                       "threshold": float(thresholds[4 * fold]), "auroc": -42,
                       "checkpoint_path": "private-subject-do-not-export"} for fold in range(3)],
        }
    return result


def test_recomputes_metrics_confusion_counts_and_fold_statistics(reports):
    result = summary.summarize(reports, bootstrap=20)
    assert result["cohort"] == {"sample_count": 12, "positive_count": 6, "negative_count": 6, "fold_count": 3}
    assert all(result["validation"].values())
    for name, model in result["models"].items():
        oof = reports[name]["oof"]
        labels, probs, flags = (np.array(oof[key]) for key in ("labels", "probabilities", "predictions"))
        metrics = model["pooled_metrics"]
        assert metrics["auroc"] == roc_auc_score(labels, probs)
        assert metrics["average_precision"] == average_precision_score(labels, probs)
        assert metrics["brier_score"] == brier_score_loss(labels, probs)
        for key, label, flag in (("tp", 1, 1), ("tn", 0, 0), ("fp", 0, 1), ("fn", 1, 0)):
            assert metrics[key] == int(((labels == label) & (flags == flag)).sum())
        assert metrics["sensitivity"] == metrics["tp"] / 6
        assert metrics["specificity"] == metrics["tn"] / 6
        aucs = [roc_auc_score(labels[start:start + 4], probs[start:start + 4]) for start in (0, 4, 8)]
        assert [fold["auroc"] for fold in model["folds"]] == aucs
        assert model["fold_auroc_mean"] == np.mean(aucs)
        assert model["fold_auroc_std"] == np.std(aucs, ddof=1)
        assert model["fold_auroc_std_ddof"] == 1
    assert result["models"][summary.V3]["pooled_metrics"]["tp"] == 6  # Includes exact threshold ties.
    assert "private-subject" not in json.dumps(result, allow_nan=False)
    assert not {"oof", "indices", "labels", "probabilities", "predictions", "thresholds"} & set(result)
    assert "not external validation" in result["bootstrap"]["scope"]
    assert "not repeated-training uncertainty" in result["bootstrap"]["scope"]
    assert "calibration" in " ".join(result["notes"])


@pytest.mark.parametrize("bootstrap", [20, 37])
def test_bootstrap_is_deterministic_stratified_and_paired_against_reference(reports, bootstrap):
    before = copy.deepcopy(reports)
    result = summary.summarize(reports, bootstrap=bootstrap)
    assert result == summary.summarize(dict(reversed(list(reports.items()))), bootstrap=bootstrap)
    assert reports == before
    rng = np.random.default_rng(2026)
    groups = [np.array([start, start + 2]) for start in (0, 1, 4, 5, 8, 9)]
    labels = np.array(reports[summary.V3]["oof"]["labels"])
    draws = []
    for _ in range(bootstrap):
        selected = np.concatenate([rng.choice(group, 2, replace=True) for group in groups])
        draws.append([roc_auc_score(labels[selected], np.array(reports[name]["oof"]["probabilities"])[selected])
                      for name in summary.MODELS])
    draws = np.array(draws)
    assert result["bootstrap"]["seed"] == 2026
    assert result["bootstrap"]["resamples"] == bootstrap
    assert result["bootstrap"]["strata"] == ["fold", "label"]
    assert result["bootstrap"]["paired_across_models"] is True
    for column, name in enumerate(summary.MODELS):
        assert result["models"][name]["auroc_ci95"] == pytest.approx(np.percentile(draws[:, column], [2.5, 97.5]))
    for name in ("ast_clinical", "clinical_only"):
        delta = result["paired_deltas"][f"{name}_minus_v3"]
        assert delta["reference"] == summary.V3 and delta["model"] == name
        expected = result["models"][name]["pooled_metrics"]["auroc"] - result["models"][summary.V3]["pooled_metrics"]["auroc"]
        assert delta["auroc_delta"] == expected
        assert delta["auroc_delta_ci95"] == pytest.approx(np.percentile(draws[:, summary.MODELS.index(name)] - draws[:, 0], [2.5, 97.5]))


def test_identical_models_have_zero_paired_delta_interval(reports):
    for name in ("ast_clinical", "clinical_only"):
        reports[name] = copy.deepcopy(reports[summary.V3])
    result = summary.summarize(reports, bootstrap=20)
    for delta in result["paired_deltas"].values():
        assert delta["auroc_delta"] == 0
        assert delta["auroc_delta_ci95"] == [0, 0]


def test_subject_resampling_preserves_fold_label_counts_with_replacement(reports):
    oof = {key: np.array(value) for key, value in reports[summary.V3]["oof"].items()}
    repeated_subject = False
    for selected in summary._subject_resamples(oof, 20):
        assert len(selected) == 12
        repeated_subject |= len(set(selected)) < 12
        for fold in range(3):
            for label in (0, 1):
                assert ((oof["folds"][selected] == fold) & (oof["labels"][selected] == label)).sum() == 2
    assert repeated_subject


@pytest.mark.parametrize("field,value", [
    ("indices", -1), ("indices", 12), ("indices", 1), ("indices", 0.0), ("indices", True),
    ("indices", "private-subject-do-not-export"), ("folds", -1), ("folds", 0.5), ("folds", True),
    ("folds", 99), ("labels", 2), ("labels", -1), ("labels", float("nan")),
    ("probabilities", float("nan")), ("probabilities", float("inf")), ("probabilities", -0.01),
    ("probabilities", 1.01), ("probabilities", "0.1"), ("probabilities", [0.1]),
    ("thresholds", float("nan")), ("thresholds", float("inf")), ("thresholds", -0.01),
    ("thresholds", 1.01), ("thresholds", 0.51), ("predictions", 2), ("predictions", True),
])
def test_rejects_invalid_oof_values_without_disclosing_subjects(reports, field, value):
    reports[summary.V3]["oof"][field][0] = value
    with pytest.raises(ValueError) as error:
        summary.summarize(reports, bootstrap=20)
    assert "private-subject" not in str(error.value)


@pytest.mark.parametrize("field", ["indices", "labels", "folds"])
def test_rejects_misalignment_instead_of_silently_sorting(reports, field):
    model = reports["ast_clinical"]
    if field == "folds":
        model["oof"][field] = [2 - fold for fold in model["oof"][field]]
        for fold in model["folds"]:
            fold["fold"] = 2 - fold["fold"]
    else:
        values = model["oof"][field]
        values[0], values[1] = values[1], values[0]
    with pytest.raises(ValueError, match="exactly aligned"):
        summary.summarize(reports, bootstrap=20)


@pytest.mark.parametrize("problem", ["missing_model", "extra_model", "missing_oof", "missing_field", "empty", "length", "missing_subject", "single_class", "fold_counts", "duplicate_fold", "missing_fold", "fold_threshold", "fold_boolean"])
def test_rejects_incomplete_or_inconsistent_reports(reports, problem):
    model = reports[summary.V3]
    if problem == "missing_model":
        reports.pop("ast_audio")
    elif problem == "extra_model":
        reports["unexpected"] = copy.deepcopy(model)
    elif problem == "missing_oof":
        model.pop("oof")
    elif problem == "missing_field":
        model["oof"].pop("thresholds")
    elif problem in ("empty", "length"):
        model["oof"]["probabilities"] = [] if problem == "empty" else [0.1]
    elif problem == "missing_subject":
        for values in model["oof"].values():
            values.pop()
    elif problem == "single_class":
        model["oof"]["labels"][:4] = [0] * 4
    elif problem == "fold_counts":
        model["folds"][0]["sample_count"] += 1
    elif problem == "duplicate_fold":
        model["folds"][1]["fold"] = 0
    elif problem == "missing_fold":
        model["folds"].pop()
    else:
        model["folds"][0]["threshold" if problem == "fold_threshold" else "fold"] = float("nan") if problem == "fold_threshold" else False
    with pytest.raises(ValueError):
        summary.summarize(reports, bootstrap=20)


@pytest.mark.parametrize("bootstrap", [0, -1, 19, True, 20.0, "20"])
def test_rejects_invalid_library_bootstrap_counts(reports, bootstrap):
    with pytest.raises(ValueError, match="integer >= 20"):
        summary.summarize(reports, bootstrap=bootstrap)


@pytest.mark.parametrize("value", ["20", "999", "-1", "2.5", "bad"])
def test_cli_rejects_less_than_thousand_or_non_integer_bootstrap(tmp_path, value, capsys):
    with pytest.raises(SystemExit) as error:
        summary.main(["--output-dir", str(tmp_path), "--bootstrap", value])
    assert error.value.code == 2
    assert "integer >= 1000" in capsys.readouterr().err
    assert not (tmp_path / "summary.json").exists()


def test_cli_writes_summary_prints_table_and_never_overwrites(reports, tmp_path, capsys):
    originals = {}
    for filename, models in summary.SOURCES.items():
        path = tmp_path / filename
        path.write_text(json.dumps({name: reports[name] for name in models}), encoding="utf-8")
        originals[path] = path.read_bytes()
    summary.main(["--output-dir", str(tmp_path)])
    output = capsys.readouterr().out
    destination = tmp_path / "summary.json"
    content = destination.read_bytes()
    result = json.loads(content)
    assert result["bootstrap"]["resamples"] == 2000
    assert result["bootstrap"]["seed"] == 2026
    assert "AUROC [95% CI]" in output and "Fold mean +/- SD" in output
    assert "TP TN FP FN" in output and "ast_clinical_minus_v3" in output
    assert "private-subject" not in output + content.decode()
    with pytest.raises(SystemExit) as error:
        summary.main(["--output-dir", str(tmp_path)])
    assert error.value.code == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert destination.read_bytes() == content
    assert all(path.read_bytes() == original for path, original in originals.items())


def test_cli_invalid_source_leaves_no_summary(tmp_path, capsys):
    (tmp_path / "cnn-reports.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        summary.main(["--output-dir", str(tmp_path), "--bootstrap", "1000"])
    assert error.value.code == 2
    assert "expected benchmark models" in capsys.readouterr().err
    assert not (tmp_path / "summary.json").exists()
