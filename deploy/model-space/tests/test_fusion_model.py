from __future__ import annotations

import numpy as np
import pytest
import torch

from src.metadata import (
    CODA_TB_COUNTRIES,
    UNVALIDATED_COUNTRIES,
    encode_clinical_metadata,
    validate_metadata,
)
from src.model import (
    RESIDUAL_FUSION_CNN_V3,
    RESIDUAL_SPECTROGRAM_CNN_V2,
    RESIDUAL_TABULAR_FUSION_V4,
    GatedFusion,
    ResidualFusionClassifier,
    ResidualTabularFusionClassifier,
    TabularEncoder,
    build_screening_model,
)
from training.encoding import CLINICAL_FEATURE_ORDER, ClinicalPreprocessor
from src.pretrained_audio import (
    TeacherConfig,
    TeacherEmbeddingCache,
    distillation_loss,
)
from tests.factories.metadata import build_metadata


N_MELS = 64
TARGET_FRAMES = 101
METADATA_DIM = len(CLINICAL_FEATURE_ORDER)


def _clips(batch: int = 2, clip_count: int = 3) -> torch.Tensor:
    return torch.zeros(batch, clip_count, 1, N_MELS, TARGET_FRAMES)


# ── Arsitektur v4 ───────────────────────────────────────────────────────────


def test_v4_tabular_branch_is_much_larger_than_v3() -> None:
    """The measured justification for v4: demographic variables score 0.834
    AUROC alone on CODA-TB, higher than the audio branch. A 3,872-parameter
    clinical MLP cannot carry that."""
    v3_clinical = sum(
        p.numel()
        for p in ResidualFusionClassifier(metadata_dim=METADATA_DIM).clinical_encoder.parameters()
    )
    v4_tabular = sum(
        p.numel()
        for p in ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).tabular_encoder.parameters()
    )
    assert v4_tabular > 5 * v3_clinical


def test_v4_stays_close_to_v3_in_total_size() -> None:
    """The artifact ships to a CPU Space; a much larger model would trade the
    deployment budget for an unverifiable AUROC gain."""
    v3 = sum(p.numel() for p in ResidualFusionClassifier(metadata_dim=METADATA_DIM).parameters())
    v4 = sum(p.numel() for p in ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).parameters())
    assert v4 > v3
    assert v4 < v3 * 1.5


def test_v4_forward_returns_patient_logits() -> None:
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM)
    logits = model(
        _clips(), torch.zeros(2, METADATA_DIM), clip_mask=torch.ones(2, 3, dtype=torch.bool)
    )
    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()


def test_v4_forward_clips_matches_the_v2_v3_contract() -> None:
    """The trainer calls forward_clips with a 4D batch; a 5D-only signature
    would break every training run."""
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM)
    assert model.forward_clips(torch.zeros(7, 1, N_MELS, TARGET_FRAMES)).shape == (7, 2)
    with pytest.raises(ValueError, match=r"\(clips, 1,"):
        model.forward_clips(torch.zeros(2, 3, 1, N_MELS, TARGET_FRAMES))


def test_v4_tabular_branch_handles_a_batch_of_one() -> None:
    """Small cohorts produce singleton batches. BatchNorm1d raises on those,
    which is why the branch uses LayerNorm."""
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).train()
    logits = model(
        _clips(1, 2), torch.zeros(1, METADATA_DIM), clip_mask=torch.ones(1, 2, dtype=torch.bool)
    )
    assert logits.shape == (1, 2)


def test_v4_uses_clinical_metadata() -> None:
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).eval()
    clips = _clips()
    mask = torch.ones(2, 3, dtype=torch.bool)
    low = torch.zeros(2, METADATA_DIM)
    high = torch.zeros(2, METADATA_DIM)
    high[:, CLINICAL_FEATURE_ORDER.index("hiv_Positive")] = 1.0
    with torch.inference_mode():
        assert not torch.allclose(model(clips, low, mask), model(clips, high, mask))


def test_v4_gate_makes_audio_and_clinical_interact() -> None:
    """With a dead gate the clinical half passes through untouched."""
    fusion = GatedFusion(8, 8, 8).eval()
    with torch.no_grad():
        fusion.gate.weight.zero_()
        fusion.gate.bias.zero_()
    audio = torch.randn(4, 8)
    clinical = torch.randn(4, 8)
    with torch.inference_mode():
        embedded = fusion.joint(torch.cat([audio, clinical], dim=1))
        assert torch.allclose(embedded, fusion(audio, clinical), atol=1e-6)


def test_v4_gate_responds_to_a_biased_gate() -> None:
    fusion = GatedFusion(8, 8, 8).eval()
    with torch.no_grad():
        fusion.gate.bias[8:] = 5.0
    audio = torch.randn(4, 8)
    with torch.inference_mode():
        assert not torch.allclose(
            fusion(audio, torch.zeros(4, 8)), fusion(audio, torch.ones(4, 8)), atol=1e-6
        )


def test_tabular_encoder_rejects_empty_metadata() -> None:
    with pytest.raises(ValueError, match="metadata_dim must be positive"):
        TabularEncoder(0)


def test_v4_is_gated_to_fusion_input() -> None:
    with pytest.raises(ValueError, match="requires fusion"):
        build_screening_model(
            RESIDUAL_TABULAR_FUSION_V4,
            metadata_dim=METADATA_DIM,
            input_mode="audio",
            expected_n_mels=N_MELS,
            expected_target_frames=TARGET_FRAMES,
        )


def test_v4_is_routed_by_the_factory() -> None:
    model = build_screening_model(
        RESIDUAL_TABULAR_FUSION_V4,
        metadata_dim=METADATA_DIM,
        input_mode="fusion",
        expected_n_mels=N_MELS,
        expected_target_frames=TARGET_FRAMES,
    )
    assert isinstance(model, ResidualTabularFusionClassifier)


def test_v3_and_v4_both_remain_routable() -> None:
    for architecture, expected in (
        (RESIDUAL_FUSION_CNN_V3, "ResidualFusionClassifier"),
        (RESIDUAL_TABULAR_FUSION_V4, "ResidualTabularFusionClassifier"),
    ):
        built = build_screening_model(
            architecture,
            metadata_dim=METADATA_DIM,
            input_mode="fusion",
            expected_n_mels=N_MELS,
            expected_target_frames=TARGET_FRAMES,
        )
        assert type(built).__name__ == expected


def test_v4_padding_does_not_leak_between_patients() -> None:
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).eval()
    clips = torch.zeros(2, 3, 1, N_MELS, TARGET_FRAMES)
    mask = torch.tensor([[True, False, False], [True, True, True]])
    metadata = torch.zeros(2, METADATA_DIM)
    mutated = clips.clone()
    mutated[0, 1:] = 9.0
    with torch.inference_mode():
        assert torch.allclose(model(clips, metadata, mask)[0], model(mutated, metadata, mask)[0], atol=1e-6)


def test_v4_ignores_padded_clip_contents() -> None:
    model = ResidualTabularFusionClassifier(metadata_dim=METADATA_DIM).eval()
    real = torch.randn(1, 1, 1, N_MELS, TARGET_FRAMES)
    padded = torch.cat([real, torch.randn(1, 4, 1, N_MELS, TARGET_FRAMES)], dim=1)
    mask = torch.tensor([[True, False, False, False, False]])
    metadata = torch.zeros(1, METADATA_DIM)
    with torch.inference_mode():
        assert torch.allclose(model(real, metadata, None), model(padded, metadata, mask), atol=1e-6)


# ── Loss risk-balanced ──────────────────────────────────────────────────────


def test_risk_balanced_loss_defaults_to_plain_cross_entropy() -> None:
    from training.runner import risk_balanced_loss

    logits = torch.randn(8, 2)
    labels = torch.randint(0, 2, (8,))
    weights = torch.tensor([1.0, 3.0])
    assert float(risk_balanced_loss(logits, labels, class_weights=weights)) == pytest.approx(
        float(torch.nn.functional.cross_entropy(logits, labels, weight=weights)), abs=1e-6
    )


def test_risk_balanced_penalty_only_raises_the_positive_class() -> None:
    from training.runner import risk_balanced_loss

    logits = torch.zeros(4, 2)
    labels = torch.zeros(4, dtype=torch.long)
    base = float(risk_balanced_loss(logits, labels, false_negative_penalty=1.0))
    penalised = float(risk_balanced_loss(logits, labels, false_negative_penalty=3.0))
    # Every label is negative, so raising the positive cost must not move the
    # loss. If it does, the penalty is leaking onto the wrong class.
    assert penalised == pytest.approx(base, abs=1e-6)


def test_risk_balanced_penalty_increases_cost_of_missing_tb() -> None:
    """A missed TB case is a true label of 1 predicted as 0.

    The probe needs a mixed batch: PyTorch normalises ``weight`` by the sum of
    the target-class weights, so in a single-sample batch the penalty cancels
    out and the test would pass for the wrong reason.
    """
    from training.runner import risk_balanced_loss

    # One negative predicted correctly, and one positive predicted as negative:
    # same confident prediction, different truth, so the second is a miss.
    logits = torch.tensor([[5.0, -5.0], [5.0, -5.0]])
    labels = torch.tensor([0, 1])
    cheap = float(risk_balanced_loss(logits, labels, false_negative_penalty=1.0))
    strict = float(risk_balanced_loss(logits, labels, false_negative_penalty=3.0))
    assert strict > cheap


def test_risk_balanced_penalty_does_not_move_correct_predictions() -> None:
    """Raising the cost of a miss must not also make correct negatives worse;
    the penalty is a reweighting, not a global inflation."""
    from training.runner import risk_balanced_loss

    logits = torch.tensor([[5.0, -5.0], [5.0, -5.0]])
    labels = torch.tensor([0, 0])
    cheap = float(risk_balanced_loss(logits, labels, false_negative_penalty=1.0))
    strict = float(risk_balanced_loss(logits, labels, false_negative_penalty=3.0))
    assert strict == pytest.approx(cheap, abs=1e-6)


def test_risk_balanced_loss_rejects_a_nonpositive_penalty() -> None:
    from training.runner import risk_balanced_loss

    with pytest.raises(ValueError, match="must be positive"):
        risk_balanced_loss(
            torch.randn(4, 2), torch.zeros(4, dtype=torch.long), false_negative_penalty=0.0
        )


def test_risk_balanced_loss_does_not_mutate_caller_weights() -> None:
    from training.runner import risk_balanced_loss

    weights = torch.tensor([1.0, 2.0])
    before = weights.clone()
    risk_balanced_loss(
        torch.randn(4, 2),
        torch.zeros(4, dtype=torch.long),
        class_weights=weights,
        false_negative_penalty=5.0,
    )
    assert torch.equal(weights, before)


# ── Arsitektur v3 ───────────────────────────────────────────────────────────


def test_fusion_model_matches_student_scale() -> None:
    """The student must stay small enough for a CPU Space, or the whole
    distillation argument (small artifact, from-scratch student) is lost."""
    v2 = build_screening_model(
        RESIDUAL_SPECTROGRAM_CNN_V2,
        metadata_dim=0,
        input_mode="audio",
        expected_n_mels=N_MELS,
        expected_target_frames=TARGET_FRAMES,
    )
    v3 = ResidualFusionClassifier(metadata_dim=METADATA_DIM)
    v2_params = sum(p.numel() for p in v2.parameters())
    v3_params = sum(p.numel() for p in v3.parameters())
    assert v3_params > v2_params
    # Fusion must not turn into a larger backbone.
    assert v3_params < v2_params * 1.5


def test_fusion_forward_returns_patient_level_logits() -> None:
    model = ResidualFusionClassifier(metadata_dim=METADATA_DIM)
    logits = model(
        _clips(),
        torch.zeros(2, METADATA_DIM),
        clip_mask=torch.ones(2, 3, dtype=torch.bool),
    )
    assert logits.shape == (2, 2)
    assert torch.isfinite(logits).all()


def test_fusion_actually_uses_clinical_metadata() -> None:
    """Regression guard for the original defect: v2 collected 16 clinical
    fields and then discarded them. Identical audio with different clinical
    vectors must produce different logits."""
    model = ResidualFusionClassifier(metadata_dim=METADATA_DIM).eval()
    clips = _clips()
    mask = torch.ones(2, 3, dtype=torch.bool)
    low = torch.zeros(2, METADATA_DIM)
    high = torch.zeros(2, METADATA_DIM)
    high[:, CLINICAL_FEATURE_ORDER.index("hiv_Positive")] = 1.0
    with torch.inference_mode():
        first = model(clips, low, mask)
        second = model(clips, high, mask)
    assert not torch.allclose(first, second)


def test_fusion_rejects_mismatched_metadata_width() -> None:
    model = ResidualFusionClassifier(metadata_dim=METADATA_DIM)
    with pytest.raises(ValueError, match="metadata"):
        model(_clips(), torch.zeros(2, 5), clip_mask=torch.ones(2, 3, dtype=torch.bool))


def test_fusion_rejects_wrong_spectrogram_shape() -> None:
    model = ResidualFusionClassifier(metadata_dim=METADATA_DIM)
    with pytest.raises(ValueError, match="clips must have shape"):
        model.forward_clips(torch.zeros(2, 1, 32, 50))


def test_fusion_is_gated_to_fusion_input() -> None:
    with pytest.raises(ValueError, match="requires fusion"):
        build_screening_model(
            RESIDUAL_FUSION_CNN_V3,
            metadata_dim=0,
            input_mode="audio",
            expected_n_mels=N_MELS,
            expected_target_frames=TARGET_FRAMES,
        )


def test_fusion_is_gated_to_positive_metadata_dim() -> None:
    with pytest.raises(ValueError, match="requires fusion"):
        build_screening_model(
            RESIDUAL_FUSION_CNN_V3,
            metadata_dim=0,
            input_mode="fusion",
            expected_n_mels=N_MELS,
            expected_target_frames=TARGET_FRAMES,
        )


def test_v2_still_rejects_fusion_input() -> None:
    """v2 is a versioned, released architecture; its contract must not drift."""
    with pytest.raises(ValueError, match="only supports audio"):
        build_screening_model(
            RESIDUAL_SPECTROGRAM_CNN_V2,
            metadata_dim=METADATA_DIM,
            input_mode="fusion",
            expected_n_mels=N_MELS,
            expected_target_frames=TARGET_FRAMES,
        )


# ── Preprocessor klinis ─────────────────────────────────────────────────────


def _as_csv_rows(rows):
    """CODA metadata arrives as CSV, so every value is a string there. The API
    path sends real numbers. Both must encode identically."""
    return [{k: ("" if v is None else str(v)) for k, v in row.items()} for row in rows]


def _row(**overrides):
    row = {
        "sex": "Male",
        "age": "40",
        "height": "170",
        "weight": "65",
        "reported_cough_dur": "30",
        "heart_rate": "80",
        "temperature": "37.0",
        "Country": "PH",
        "HIVstatus": "Negative",
    }
    row.update(overrides)
    return row


def test_preprocessor_fit_requires_rows() -> None:
    with pytest.raises(ValueError, match="at least one clinical row"):
        ClinicalPreprocessor.fit([])


def test_preprocessor_output_dimension() -> None:
    preprocessor = ClinicalPreprocessor.fit([_row()])
    vector = preprocessor.transform(_row(), cough_count=3)
    assert vector.shape == (METADATA_DIM,)
    assert vector.dtype == np.float32


def test_preprocessor_uses_z_a_not_s_a() -> None:
    """ZA is South Africa. The old constant said SA, so an African participant
    offered by the UI could never be encoded."""
    assert "country_ZA" in CLINICAL_FEATURE_ORDER
    assert "country_SA" not in CLINICAL_FEATURE_ORDER


def test_preprocessor_countries_come_from_single_source() -> None:
    preprocessor = ClinicalPreprocessor.fit([_row()])
    assert preprocessor.countries == tuple(sorted(CODA_TB_COUNTRIES))


def test_preprocessor_accepts_coda_sa_as_south_africa() -> None:
    """CODA's Country column contains "SA" and never "ZA". Verified against
    CODA_TB_additional_variables_train.csv, where SA covers 137 of 1,105
    participants. Reading it as anything but South Africa would silently drop
    12% of the cohort."""
    preprocessor = ClinicalPreprocessor.fit([_row()])
    vector = preprocessor.transform(_row(Country="SA"), cough_count=1)
    assert vector[CLINICAL_FEATURE_ORDER.index("country_ZA")] == pytest.approx(1.0)
    assert vector[CLINICAL_FEATURE_ORDER.index("country_IN")] == pytest.approx(0.0)


def test_preprocessor_maps_dataset_codes_to_iso_codes() -> None:
    from src.metadata import normalise_country

    assert normalise_country("SA") == "ZA"
    assert normalise_country("za") == "ZA"
    assert normalise_country(" sa ") == "ZA"
    assert normalise_country("PH") == "PH"
    assert normalise_country("") == ""


def test_preprocessor_rejects_a_country_outside_the_distribution() -> None:
    """An unknown country must fail loudly rather than encode to all-zero
    features, which is indistinguishable from a missing value."""
    preprocessor = ClinicalPreprocessor.fit([_row()])
    with pytest.raises(ValueError, match="outside the training distribution"):
        preprocessor.transform(_row(Country="BR"), cough_count=1)


def test_api_accepts_sa_and_normalises_it_to_za() -> None:
    from src.metadata import normalise_country, validate_metadata

    from tests.factories.metadata import build_metadata

    parsed = validate_metadata(build_metadata(Country="SA"))
    assert parsed.country == "ZA"
    assert not parsed.is_country_out_of_distribution
    assert normalise_country("SA") == "ZA"


def test_preprocessor_encodes_cough_count() -> None:
    preprocessor = ClinicalPreprocessor.fit([_row()])
    vector = preprocessor.transform(_row(), cough_count=7)
    index = CLINICAL_FEATURE_ORDER.index("Numberofcoughsoundscollected")
    assert vector[index] == pytest.approx(7.0)


def test_preprocessor_imputes_missing_numeric_with_train_mean() -> None:
    rows = [_row(age="20"), _row(age="40"), _row(age="60")]
    preprocessor = ClinicalPreprocessor.fit(rows)
    missing = preprocessor.transform(_row(age=""), cough_count=1)
    complete = preprocessor.transform(_row(age="40"), cough_count=1)
    index = CLINICAL_FEATURE_ORDER.index("age")
    assert missing[index] == pytest.approx(0.0, abs=1e-6)
    assert complete[index] == pytest.approx(0.0, abs=1e-6)


def test_preprocessor_rejects_unknown_hiv_status() -> None:
    preprocessor = ClinicalPreprocessor.fit([_row()])
    with pytest.raises(ValueError, match="HIVstatus"):
        preprocessor.transform(_row(HIVstatus="Maybe"), cough_count=1)


def test_training_and_inference_encoders_agree() -> None:
    """The single most important invariant: the student is trained on one
    encoding and served another if these two ever drift apart."""
    rows = [
        {**build_metadata(age=20, sex="Male"), **{}},
        {**build_metadata(age=60, sex="Female")},
    ]
    preprocessor = ClinicalPreprocessor.fit(_as_csv_rows(rows))

    csv_row = _as_csv_rows(
        [build_metadata(age=33, sex="Female", Country="ZA", HIVstatus="Positive")]
    )[0]
    json_row = build_metadata(age=33, sex="Female", Country="ZA", HIVstatus="Positive")

    trained = preprocessor.transform(csv_row, cough_count=4)
    served = encode_clinical_metadata(
        validate_metadata(json_row), preprocessor.to_dict(), cough_count=4
    )
    assert np.array_equal(trained, served)


# ── Gate cakupan negara ─────────────────────────────────────────────────────


def test_indonesia_is_outside_training_but_explicitly_unvalidated() -> None:
    assert "ID" not in CODA_TB_COUNTRIES
    assert "ID" in UNVALIDATED_COUNTRIES


def test_kenya_is_supported_because_the_manifest_declares_it() -> None:
    """The manifest declared ["KE"] while the gate excluded it, so a trained
    TBscreen model could never be served."""
    from src.metadata import SUPPORTED_CODA_COUNTRIES

    assert "KE" in SUPPORTED_CODA_COUNTRIES


# ── Distillation ────────────────────────────────────────────────────────────


def test_distillation_loss_is_zero_when_student_equals_teacher() -> None:
    logits = torch.randn(8, 2)
    assert float(distillation_loss(logits, logits.clone(), weight=0.3)) == pytest.approx(0.0, abs=1e-6)


def test_distillation_loss_matches_reference_kl() -> None:
    student = torch.randn(8, 2)
    teacher = torch.randn(8, 2)
    ours = float(distillation_loss(student, teacher, weight=0.3, temperature=2.0))
    import torch.nn.functional as F

    reference = (
        F.kl_div(
            F.log_softmax(student / 2.0, dim=1),
            F.softmax(teacher / 2.0, dim=1),
            reduction="batchmean",
        )
        * (2.0**2)
        * 0.3
    )
    assert ours == pytest.approx(float(reference), abs=1e-5)


def test_distillation_never_backpropagates_into_teacher() -> None:
    student = torch.randn(8, 2, requires_grad=True)
    teacher = torch.randn(8, 2, requires_grad=True)
    distillation_loss(student, teacher, weight=0.3).backward()
    assert teacher.grad is None or bool((teacher.grad == 0).all())
    assert student.grad is not None


def test_distillation_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="must match"):
        distillation_loss(torch.randn(8, 2), torch.randn(8, 5), weight=0.3)


@pytest.mark.parametrize("weight", [0.0, 1.0, 1.5, -0.2])
def test_distillation_rejects_weight_outside_open_unit_interval(weight: float) -> None:
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        distillation_loss(torch.randn(4, 2), torch.randn(4, 2), weight=weight)


def test_teacher_config_rejects_out_of_range_settings() -> None:
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        TeacherConfig(weight=1.0)
    with pytest.raises(ValueError, match="temperature must be positive"):
        TeacherConfig(temperature=0.0)
    with pytest.raises(ValueError, match="batch_size"):
        TeacherConfig(batch_size=0)


# ── Cache embedding guru ────────────────────────────────────────────────────


def test_teacher_cache_is_keyed_by_teacher_identity() -> None:
    """A cache warmed by one teacher must not be served to another."""
    assert TeacherEmbeddingCache.key_for(b"abc", "teacher-a") != TeacherEmbeddingCache.key_for(
        b"abc", "teacher-b"
    )


def test_teacher_cache_roundtrip(tmp_path) -> None:
    path = tmp_path / "teacher.npz"
    cache = TeacherEmbeddingCache(path)
    first = np.arange(8, dtype=np.float32)
    second = np.ones(8, dtype=np.float32)
    cache.put("k1", first)
    cache.put("k2", second)
    cache.flush()

    reloaded = TeacherEmbeddingCache(path)
    assert reloaded.size == 2
    assert reloaded.dim == 8
    assert np.array_equal(reloaded.get("k1"), first)
    assert reloaded.get("missing") is None


def test_teacher_cache_put_overwrites_existing_key(tmp_path) -> None:
    cache = TeacherEmbeddingCache(tmp_path / "teacher.npz")
    cache.put("k", np.zeros(4, dtype=np.float32))
    cache.put("k", np.ones(4, dtype=np.float32))
    assert cache.size == 1
    assert np.array_equal(cache.get("k"), np.ones(4))


def test_teacher_cache_refuses_to_write_inconsistent_dimensions(tmp_path) -> None:
    cache = TeacherEmbeddingCache(tmp_path / "teacher.npz")
    cache.put("k1", np.zeros(4, dtype=np.float32))
    cache.put("k2", np.zeros(8, dtype=np.float32))
    with pytest.raises(ValueError, match="inconsistent dimensions"):
        cache.flush()


def test_teacher_cache_refuses_to_write_empty(tmp_path) -> None:
    cache = TeacherEmbeddingCache(tmp_path / "teacher.npz")
    with pytest.raises(ValueError, match="empty teacher cache"):
        cache.flush()
