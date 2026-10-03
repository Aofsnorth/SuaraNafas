"""Patient-level cross-validation for the audio + clinical fusion model.

``cross_validate.py`` trains the audio-only residual CNN and emits
``input_mode="audio"`` / ``metadata_dim=0``, so the clinical tensor collected
by the screening form is discarded (``ResidualSpectrogramClassifier.forward``
does ``del metadata``). Published work on this task reports a large gain from
adding routinely collected clinical variables, so this module trains
``residual_fusion_cnn_v3`` instead.

Two rules are enforced here and are the reason this file exists:

1. The clinical preprocessor is fitted on the *training* partition only. Fitting
   standardisation statistics on the full cohort would leak test-fold means and
   standard deviations into training.
2. Splitting happens at patient level, so no participant's coughs appear in
   both training and test data.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from src.audio_features import (
    AudioFeatureConfig,
    SpecAugmentConfig,
    extract_log_mel,
    spec_augment,
)
from src.model import (
    RESIDUAL_FUSION_CNN_V3,
    RESIDUAL_TABULAR_FUSION_V4,
    ResidualFusionClassifier,
    ResidualTabularFusionClassifier,
)
from training.dataset import PatientExample
from training.encoding import ClinicalPreprocessor
from training.evaluator import evaluate_model
from training.metrics import (
    calculate_binary_metrics,
    select_threshold_for_minimum_sensitivity,
)
from training.pipeline import build_candidate_manifest
from training.runner import train_one_epoch
from training.split import split_by_patient
from training.train import _resolve_device, _set_seed


LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
DEFAULT_ELEVATED_SENSITIVITY = 0.80
DEFAULT_HIGHER_SENSITIVITY = 0.90
DEFAULT_FOLDS = 5


@dataclass(frozen=True)
class FusionPatient:
    """One participant's padded-free clip stack plus a single clinical vector."""

    patient_id: str
    label: int
    clips: np.ndarray
    clinical: np.ndarray
    # Per-clip teacher logits (clips, 2), fitted on this patient's training
    # fold only. None disables distillation for this patient.
    teacher_logits: np.ndarray | None = None


def _new_fusion_model(
    metadata_dim: int,
    audio_config: AudioFeatureConfig,
    device: torch.device,
    architecture: str = RESIDUAL_FUSION_CNN_V3,
) -> ResidualFusionClassifier | ResidualTabularFusionClassifier:
    """Construct a fusion model without loading any weights.

    The architecture is a parameter so the same patient-level protocol can
    score v3 and v4 on identical splits. Comparing them on different folds
    would measure the split, not the model.
    """
    if architecture == RESIDUAL_TABULAR_FUSION_V4:
        return ResidualTabularFusionClassifier(
            metadata_dim=metadata_dim,
            expected_n_mels=audio_config.n_mels,
            expected_target_frames=audio_config.target_frames,
        ).to(device)
    if architecture == RESIDUAL_FUSION_CNN_V3:
        return ResidualFusionClassifier(
            metadata_dim=metadata_dim,
            expected_n_mels=audio_config.n_mels,
            expected_target_frames=audio_config.target_frames,
        ).to(device)
    raise ValueError(f"unsupported fusion architecture: {architecture}")


def _class_weights(patients: Sequence[FusionPatient]) -> Tensor:
    counts = torch.bincount(
        torch.tensor([patient.label for patient in patients]),
        minlength=2,
    ).float()
    if bool((counts == 0).any()):
        raise ValueError("every training partition must contain both classes")
    return counts.sum() / (counts.clamp_min(1.0) * 2.0)


def _prepare_examples(
    examples: Sequence[PatientExample],
    preprocessor: ClinicalPreprocessor,
    audio_config: AudioFeatureConfig,
    *,
    partition_name: str,
    cache: dict[Path, np.ndarray] | None = None,
    teacher_logits: dict[Path, np.ndarray] | None = None,
) -> tuple[FusionPatient, ...]:
    """Extract log-mel clips and the clinical vector for one partition.

    ``cache`` is keyed by audio path and shared across folds. Log-mel
    extraction is the dominant cost in a whole run, and every fold re-uses the
    same participants, so recomputing it per fold turns a few minutes of work
    into roughly four times as much while the GPU sits idle.
    """
    clip_count = sum(len(example.audio_paths) for example in examples)
    print(
        f"extracting {clip_count} {partition_name} clips with "
        f"{audio_config.duration_seconds:.2f}s windows"
        + (" (cache)" if cache is not None else ""),
        flush=True,
    )
    prepared: list[FusionPatient] = []
    reused = 0
    for index, example in enumerate(examples, start=1):
        per_clip: list[np.ndarray] = []
        for path in example.audio_paths:
            if cache is not None and path in cache:
                per_clip.append(cache[path])
                reused += 1
                continue
            clip = extract_log_mel(path.read_bytes(), audio_config)
            if cache is not None:
                cache[path] = clip
            per_clip.append(clip)
        clinical = preprocessor.transform(example.metadata, cough_count=len(per_clip))
        teacher = (
            None
            if teacher_logits is None
            else np.stack([teacher_logits[path] for path in example.audio_paths])
        )
        prepared.append(
            FusionPatient(
                example.patient_id,
                example.label,
                np.stack(per_clip),
                clinical,
                teacher,
            )
        )
        if index % 100 == 0 or index == len(examples):
            print(f"prepared {partition_name} subjects: {index}/{len(examples)}", flush=True)
    if reused:
        print(f"  reused {reused} cached clips in {partition_name}", flush=True)
    return tuple(prepared)


def _batches(
    patients: Sequence[FusionPatient],
    batch_size: int,
    audio_config: AudioFeatureConfig,
    augment: SpecAugmentConfig | None = None,
):
    return [
        _build_batch(patients[start : start + batch_size], audio_config, augment)
        for start in range(0, len(patients), batch_size)
    ]


def _build_batch(
    patients: Sequence[FusionPatient],
    audio_config: AudioFeatureConfig,
    augment: SpecAugmentConfig | None = None,
):
    labels = torch.tensor([patient.label for patient in patients], dtype=torch.long)
    clinical = torch.from_numpy(np.stack([patient.clinical for patient in patients]))
    max_clips = max(len(patient.clips) for patient in patients)
    padded = np.zeros(
        (
            len(patients),
            max_clips,
            1,
            audio_config.n_mels,
            audio_config.target_frames,
        ),
        dtype=np.float32,
    )
    mask = np.zeros((len(patients), max_clips), dtype=bool)
    has_teacher = all(p.teacher_logits is not None for p in patients)
    any_teacher = any(p.teacher_logits is not None for p in patients)
    if any_teacher and not has_teacher:
        raise ValueError("either every patient carries teacher logits or none do")
    teacher = (
        np.zeros((len(patients), max_clips, 2), dtype=np.float32)
        if has_teacher
        else None
    )
    for index, patient in enumerate(patients):
        clips = patient.clips
        if augment is not None:
            # Masked per clip and before padding, so the augmentation never
            # targets the zero region and cached features stay pristine.
            clips = np.stack(
                [spec_augment(clip, augment) for clip in clips]
            )
        padded[index, : len(patient.clips)] = clips
        mask[index, : len(patient.clips)] = True
        if teacher is not None:
            teacher[index, : len(patient.clips)] = patient.teacher_logits
    if teacher is None:
        # Preserve the documented 4-tuple fusion contract when distillation is
        # off, so callers that unpack four values keep working unchanged.
        return (
            torch.from_numpy(padded),
            torch.from_numpy(mask),
            clinical,
            labels,
        )
    return (
        torch.from_numpy(padded),
        torch.from_numpy(mask),
        clinical,
        labels,
        torch.from_numpy(teacher),
    )


def _shuffled(
    patients: Sequence[FusionPatient],
    *,
    seed: int,
    epoch: int,
    batch_size: int,
    audio_config: AudioFeatureConfig,
    augment: SpecAugmentConfig | None = None,
) -> list:
    ordered = list(patients)
    random.Random(seed + epoch).shuffle(ordered)
    return _batches(ordered, batch_size, audio_config, augment)


def _fit(
    train: Sequence[FusionPatient],
    validation: Sequence[FusionPatient] | None,
    *,
    epochs: int,
    batch_size: int,
    seed: int,
    device: torch.device,
    audio_config: AudioFeatureConfig,
    architecture: str = RESIDUAL_FUSION_CNN_V3,
    false_negative_penalty: float = 1.0,
    spec_augment_enabled: bool = False,
    distillation_weight: float = 0.0,
) -> tuple[dict[str, Tensor], int]:
    """Train until validation AUROC stops improving; return the best weights.

    ``validation=None`` trains for a fixed number of epochs and returns the
    final weights. That is what the released artifact uses: the epoch count
    comes from cross-validation, and re-selecting it on the full cohort would
    pick whichever epoch happens to fit its own training data best.
    """
    _set_seed(seed)
    model = _new_fusion_model(
        train[0].clinical.shape[0], audio_config, device, architecture
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    class_weights = _class_weights(train)
    validation_batches = (
        None if validation is None else _batches(validation, batch_size, audio_config)
    )
    augment = SpecAugmentConfig() if spec_augment_enabled else None

    best_state: dict[str, Tensor] | None = None
    best_epoch = 0
    best_score = float("-inf")
    for epoch in range(epochs):
        loss = train_one_epoch(
            model,
            optimizer,
            _shuffled(
                train,
                seed=seed,
                epoch=epoch,
                batch_size=batch_size,
                audio_config=audio_config,
                augment=augment,
            ),
            device=device,
            class_weights=class_weights,
            false_negative_penalty=false_negative_penalty,
            distillation_weight=distillation_weight,
        )
        if validation_batches is None:
            print(
                f"final seed={seed} epoch={epoch + 1}/{epochs} loss={loss:.4f}",
                flush=True,
            )
            continue
        score = evaluate_model(model, validation_batches, device=device).metrics["auroc"]
        numeric = float(score) if score is not None else float("-inf")
        if numeric > best_score:
            best_score = numeric
            best_epoch = epoch + 1
            best_state = copy.deepcopy(model.state_dict())
        print(
            f"fold seed={seed} epoch={epoch + 1}/{epochs} "
            f"loss={loss:.4f} val_auc={score}",
            flush=True,
        )
    if validation_batches is None:
        final_state = {
            name: value.detach().cpu()
            for name, value in model.state_dict().items()
        }
        return final_state, epochs
    if best_state is None:
        raise RuntimeError("training produced no validation checkpoint")
    return best_state, best_epoch


def _teacher_logits_for(
    examples: Sequence[PatientExample],
    *,
    teacher_model_id: str,
    cache_path: Path | None = None,
) -> dict[Path, np.ndarray]:
    """Per-clip teacher logits from a frozen AST encoder plus a linear probe.

    The probe is fitted on ``examples`` and read back on the same clips, so
    these are in-sample logits: a linear readout of a frozen AudioSet encoder
    trained on the training partition only. Fitting it on anything else would
    leak the held-out fold into the training signal.
    """
    from src.audio_features import _decode_pcm_wav
    from src.pretrained_audio import (
        TeacherConfig,
        TeacherEmbedder,
        TeacherEmbeddingCache,
        fit_teacher_probe,
    )

    config = TeacherConfig(model_id=teacher_model_id)
    embedder = TeacherEmbedder(config)
    cache = TeacherEmbeddingCache(cache_path, model_id=teacher_model_id) if cache_path else None

    paths: list[Path] = []
    labels: list[int] = []
    for example in examples:
        for path in example.audio_paths:
            paths.append(path)
            labels.append(example.label)

    embeddings: list[np.ndarray] = []
    waveforms: list[np.ndarray] = []
    pending: list[Path] = []
    for path in paths:
        hit = cache.get(TeacherEmbeddingCache.key_for(path.read_bytes(), teacher_model_id)) if cache else None
        if hit is not None:
            embeddings.append(hit)
            continue
        samples, rate = _decode_pcm_wav(path.read_bytes())
        waveforms.append(samples)
        pending.append(path)
    if waveforms:
        produced = embedder.embed_waveforms(waveforms, sample_rate=rate)
        for path, vector in zip(pending, produced):
            embeddings.append(vector)
            if cache is not None:
                cache.put(TeacherEmbeddingCache.key_for(path.read_bytes(), teacher_model_id), vector)
        if cache is not None:
            cache.flush()
    matrix = np.stack(embeddings)
    _, teacher = fit_teacher_probe(matrix, np.asarray(labels))
    return {path: teacher[index] for index, path in enumerate(paths)}


def _predict(
    state_dict: dict[str, Tensor],
    patients: Sequence[FusionPatient],
    *,
    batch_size: int,
    audio_config: AudioFeatureConfig,
    device: torch.device,
    architecture: str = RESIDUAL_FUSION_CNN_V3,
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    # Must use the same architecture that produced the checkpoint. Hardcoding
    # v3 here silently trains one model and scores with another.
    model = _new_fusion_model(
        patients[0].clinical.shape[0], audio_config, device, architecture
    )
    model.load_state_dict(state_dict, strict=True)
    result = evaluate_model(
        model,
        _batches(patients, batch_size, audio_config),
        device=device,
    )
    return result.labels, result.probabilities


def _selected_epoch(epochs: Sequence[int]) -> int:
    if not epochs or any(epoch < 1 for epoch in epochs):
        raise ValueError("selected epochs must be positive")
    return max(1, round(statistics.median(epochs)))


def run_cross_validation(
    examples: Sequence[PatientExample],
    *,
    audio_config: AudioFeatureConfig,
    folds: int,
    validation_fraction: float,
    test_fraction: float,
    epochs: int,
    batch_size: int,
    seed: int,
    device: torch.device,
    elevated_sensitivity: float,
    higher_sensitivity: float,
    architecture: str = RESIDUAL_FUSION_CNN_V3,
    false_negative_penalty: float = 1.0,
    spec_augment_enabled: bool = False,
    distillation_weight: float = 0.0,
    teacher_model_id: str = "MIT/ast-finetuned-audioset-10-10-0.4593",
    teacher_cache: Path | None = None,
) -> dict[str, object]:
    """Run repeated patient-level holdout evaluation of the fusion model."""
    if folds < 2:
        raise ValueError("at least two folds are required")

    # Shared across folds: the same clips are read by every fold, and
    # log-mel extraction is the single most expensive step in the run.
    clip_cache: dict[Path, np.ndarray] = {}
    labels: list[int] = []
    probabilities: list[float] = []
    patient_ids: list[str] = []
    selected_epochs: list[int] = []
    fold_reports: list[dict[str, object]] = []

    for fold_index in range(folds):
        # The seed differs per fold, so the holdout genuinely changes; the
        # preprocessor is refitted inside the fold and never sees the holdout.
        partitions = split_by_patient(
            examples,
            seed=seed + fold_index,
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
        )
        preprocessor = ClinicalPreprocessor.fit(
            [example.metadata for example in partitions.train]
        )
        teacher = (
            None
            if distillation_weight <= 0.0
            else _teacher_logits_for(
                partitions.train,
                teacher_model_id=teacher_model_id,
                cache_path=teacher_cache,
            )
        )
        if teacher is not None:
            print(
                f"fold-{fold_index}: teacher probe fitted on "
                f"{len(partitions.train)} training participants",
                flush=True,
            )
        train = _prepare_examples(
            partitions.train,
            preprocessor,
            audio_config,
            partition_name=f"fold-{fold_index}-train",
            cache=clip_cache,
            teacher_logits=teacher,
        )
        validation = _prepare_examples(
            partitions.validation,
            preprocessor,
            audio_config,
            partition_name=f"fold-{fold_index}-validation",
            cache=clip_cache,
        )
        test = _prepare_examples(
            partitions.test,
            preprocessor,
            audio_config,
            partition_name=f"fold-{fold_index}-test",
            cache=clip_cache,
        )
        state_dict, best_epoch = _fit(
            train,
            validation,
            epochs=epochs,
            batch_size=batch_size,
            seed=seed,
            device=device,
            audio_config=audio_config,
            architecture=architecture,
            false_negative_penalty=false_negative_penalty,
            spec_augment_enabled=spec_augment_enabled,
            distillation_weight=distillation_weight,
        )
        selected_epochs.append(best_epoch)
        fold_labels, fold_probabilities = _predict(
            state_dict,
            test,
            batch_size=batch_size,
            audio_config=audio_config,
            device=device,
            architecture=architecture,
        )
        fold_metrics = calculate_binary_metrics(fold_labels, fold_probabilities)
        labels.extend(fold_labels)
        probabilities.extend(fold_probabilities)
        patient_ids.extend(patient.patient_id for patient in test)
        fold_reports.append(
            {
                "fold": fold_index,
                "train_subjects": len(train),
                "validation_subjects": len(validation),
                "test_subjects": len(test),
                # Explicit membership lists: a patient appearing in both
                # train and test is the single most common way a cough model
                # ends up reporting a flattering score it has not earned.
                # The test list keeps the order the patients were scored in, so
                # that labels[i] and probabilities[i] are auditable against it.
                "train_patient_ids": sorted(p.patient_id for p in partitions.train),
                "validation_patient_ids": sorted(p.patient_id for p in partitions.validation),
                "test_patient_ids": [p.patient_id for p in partitions.test],
                "selected_epoch": best_epoch,
                "auroc": fold_metrics["auroc"],
            }
        )
        print(f"fold {fold_index} test auroc={fold_metrics['auroc']}", flush=True)

    pooled = calculate_binary_metrics(labels, probabilities)
    thresholds = {
        "elevated": select_threshold_for_minimum_sensitivity(
            labels, probabilities, elevated_sensitivity
        ),
        "higher": select_threshold_for_minimum_sensitivity(
            labels, probabilities, higher_sensitivity
        ),
    }
    if thresholds["elevated"] > thresholds["higher"]:
        thresholds["elevated"], thresholds["higher"] = (
            thresholds["higher"],
            thresholds["elevated"],
        )
    return {
        "pooled_metrics": pooled,
        "thresholds": thresholds,
        "folds": fold_reports,
        "selected_epoch": _selected_epoch(selected_epochs),
        "subjects": len(examples),
        "architecture": architecture,
        "false_negative_penalty": false_negative_penalty,
        # Per-participant detail, so the headline number can be audited for
        # patient overlap without re-running the training.
        "labels": labels,
        "probabilities": probabilities,
        "patient_ids": patient_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-validate the audio + clinical fusion TB screening model"
    )
    parser.add_argument("--clinical-metadata", type=Path, required=True)
    parser.add_argument("--additional-metadata", type=Path, required=True)
    parser.add_argument("--solicited-metadata", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("training-output-fusion"))
    parser.add_argument("--max-clips-per-subject", type=int, default=32)
    parser.add_argument("--folds", type=int, default=DEFAULT_FOLDS)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--architecture",
        choices=(RESIDUAL_FUSION_CNN_V3, RESIDUAL_TABULAR_FUSION_V4),
        default=RESIDUAL_TABULAR_FUSION_V4,
        help="Fusion topology to cross-validate. Both run the identical "
        "patient-level protocol, so a comparison is between models and not "
        "between splits.",
    )
    parser.add_argument(
        "--false-negative-penalty",
        type=float,
        default=1.0,
        help="Multiplier on the cost of missing a TB case. Above 1 favours "
        "sensitivity, below 1 favours specificity. This is a deployment "
        "choice, not a modelling one; 1.0 leaves the loss unweighted.",
    )
    parser.add_argument(
        "--spec-augment",
        action="store_true",
        help="Mask random time and frequency bands on training batches. Off "
        "by default so an ablation can isolate its effect.",
    )
    parser.add_argument(
        "--longitudinal-metadata",
        type=Path,
        help="CODA_TB_Longitudnal_Meta_Info.csv: natural (unprompted) coughs",
    )
    parser.add_argument(
        "--longitudinal-audio-root",
        type=Path,
        help="Directory holding the longitudinal WAVs",
    )
    parser.add_argument(
        "--distillation-weight",
        type=float,
        default=0.0,
        help="Weight of the frozen AST teacher term. 0 disables distillation. "
        "Must be strictly between 0 and 1 when set.",
    )
    parser.add_argument(
        "--require-solicited-clips",
        action="store_true",
        help="Drop participants that have no prompted (solicited) clip. Longitudinal "
        "audio adds participants who have no prompted recording, and a changing "
        "participant list reseeds the fold shuffle, which makes an ablation compare "
        "two different splits instead of two models. Set this when comparing runs.",
    )
    parser.add_argument(
        "--allow-blocked-candidate",
        action="store_true",
        help="Record a candidate manifest blocked pending external validation",
    )
    args = parser.parse_args()

    from training.dataset import load_patient_examples

    device = _resolve_device(args.device)
    audio_config = AudioFeatureConfig()
    examples = load_patient_examples(
        args.clinical_metadata,
        args.additional_metadata,
        args.solicited_metadata,
        args.audio_root,
        max_clips=args.max_clips_per_subject,
        longitudinal_metadata=args.longitudinal_metadata,
        longitudinal_audio_root=args.longitudinal_audio_root,
    )
    if args.require_solicited_clips:
        from training.dataset import read_solicited_participants

        solicited_ids = read_solicited_participants(args.solicited_metadata)
        before = len(examples)
        examples = [e for e in examples if e.patient_id in solicited_ids]
        print(
            f"note: restricted to participants with a prompted clip: "
            f"{before} -> {len(examples)}",
            flush=True,
        )
    print(f"loaded {len(examples)} CODA TB participants on {device}", flush=True)

    evaluation = run_cross_validation(
        examples,
        audio_config=audio_config,
        folds=args.folds,
        validation_fraction=args.validation_fraction,
        test_fraction=args.test_fraction,
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
        device=device,
        elevated_sensitivity=DEFAULT_ELEVATED_SENSITIVITY,
        higher_sensitivity=DEFAULT_HIGHER_SENSITIVITY,
        architecture=args.architecture,
        false_negative_penalty=args.false_negative_penalty,
        spec_augment_enabled=args.spec_augment,
        distillation_weight=args.distillation_weight,
    )

    # Refit on every participant so the released artifact sees all data, using
    # statistics from the same full cohort.
    preprocessor = ClinicalPreprocessor.fit([example.metadata for example in examples])
    all_patients = _prepare_examples(
        examples, preprocessor, audio_config, partition_name="final"
    )
    state_dict, final_epoch = _fit(
        all_patients,
        None,
        epochs=max(1, int(evaluation["selected_epoch"])),
        batch_size=args.batch_size,
        seed=args.seed,
        device=device,
        audio_config=audio_config,
        architecture=args.architecture,
        false_negative_penalty=args.false_negative_penalty,
    )
    model = _new_fusion_model(
        preprocessor.transform(
            examples[0].metadata, cough_count=len(examples[0].audio_paths)
        ).shape[0],
        audio_config,
        device,
    )
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "model-fusion.pt"
    torch.save({name: value.detach().cpu() for name, value in state_dict.items()}, artifact_path)

    preprocessing = {"audio": audio_config.to_manifest(), "clinical": preprocessor.to_dict()}
    evaluation["final_fit"] = {
        "subjects": len(all_patients),
        "epoch": final_epoch,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "device": str(device),
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "metadata_dim": preprocessor.transform(
            examples[0].metadata, cough_count=1
        ).shape[0],
    }
    evaluation["limitations"] = [
        "CODA TB is a symptomatic presumptive cohort, so community-level "
        "screening prevalence is not represented here.",
        "Fold holdouts are internal; this is not external validation.",
        "Indonesia is absent from the training distribution and any prediction "
        "for an Indonesian participant is out of distribution.",
    ]
    (output_dir / "metrics-fusion.json").write_text(
        json.dumps(evaluation, indent=2, default=str), encoding="utf-8"
    )
    build_candidate_manifest(
        artifact_path,
        output_dir / "manifest-fusion.json",
        model_name="SuaraNafas CODA TB audio-clinical fusion model",
        model_version=("5.0.0-research-candidate"
                      if args.architecture == RESIDUAL_TABULAR_FUSION_V4
                      else "4.0.0-research-candidate"),
        input_mode="fusion",
        metadata_dim=int(evaluation["final_fit"]["metadata_dim"]),
        supported_countries=list(preprocessor.countries),
        preprocessing=preprocessing,
        evaluation=evaluation,
        thresholds=evaluation["thresholds"],
        training_dataset="CODA TB DREAM solicited cough training partition",
        architecture=args.architecture,
        initialization="random_pytorch_default",
        pretrained_weights=False,
        seed=args.seed,
    )
    print(f"wrote candidate artifacts to {output_dir}", flush=True)


if __name__ == "__main__":
    main()
