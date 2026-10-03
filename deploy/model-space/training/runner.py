from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

import torch
from torch import Tensor
from torch.nn import Module
from torch.optim import Optimizer

from src.model import ResidualSpectrogramClassifier


Batch: TypeAlias = (
    tuple[Tensor | None, Tensor | None, Tensor]
    | tuple[Tensor, Tensor, Tensor, Tensor]
)


def _unpack_batch(
    batch: Batch,
) -> tuple[Tensor | None, Tensor | None, Tensor | None, Tensor, Tensor | None]:
    if len(batch) == 3:
        clips, metadata, labels = batch
        return clips, None, metadata, labels, None
    if len(batch) == 5:
        clips, clip_mask, metadata, labels, teacher_logits = batch
        return clips, clip_mask, metadata, labels, teacher_logits
    clips, clip_mask, metadata, labels = batch
    return clips, clip_mask, metadata, labels, None


def train_patient_equal_clip_epoch(
    model: ResidualSpectrogramClassifier,
    optimizer: Optimizer,
    batches: Iterable[Batch],
    *,
    device: str | torch.device = "cpu",
    class_weights: Tensor | None = None,
    false_negative_penalty: float = 1.0,
    distillation_weight: float = 0.0,
) -> float:
    """Train on clips while assigning equal total loss weight to each patient."""
    model.to(device).train()
    total_loss = 0.0
    batch_count = 0
    for batch in batches:
        clips, clip_mask, _, labels, teacher_logits = _unpack_batch(batch)
        if clips is None or clip_mask is None:
            raise ValueError("residual training requires clips and a clip mask")
        clips = clips.to(device)
        clip_mask = clip_mask.to(device)
        labels = labels.to(device).long()
        if torch.any(clip_mask.sum(dim=1) == 0):
            raise ValueError("every patient must have at least one valid clip")

        optimizer.zero_grad(set_to_none=True)
        patient_indexes = (
            torch.arange(clips.shape[0], device=device)
            .unsqueeze(1)
            .expand_as(clip_mask)[clip_mask]
        )
        clip_logits = model.forward_clips(clips[clip_mask])
        clip_losses = torch.nn.functional.cross_entropy(
            clip_logits,
            labels[patient_indexes],
            reduction="none",
        )
        patient_losses = torch.zeros(clips.shape[0], device=device)
        patient_losses.scatter_add_(0, patient_indexes, clip_losses)
        patient_losses /= clip_mask.sum(dim=1)
        if class_weights is None:
            loss = patient_losses.mean()
        else:
            weights = class_weights.to(device)[labels]
            loss = torch.sum(patient_losses * weights) / torch.sum(weights)
        if distillation_weight > 0.0:
            if teacher_logits is None:
                raise ValueError(
                    "distillation_weight is set but the batch carries no teacher logits"
                )
            from src.pretrained_audio import distillation_loss

            loss = loss + distillation_loss(
                clip_logits,
                teacher_logits.to(device)[clip_mask],
                weight=distillation_weight,
            )
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu().item())
        batch_count += 1

    if batch_count == 0:
        raise ValueError("at least one training batch is required")
    return total_loss / batch_count


def risk_balanced_loss(
    logits: Tensor,
    labels: Tensor,
    *,
    class_weights: Tensor | None = None,
    false_negative_penalty: float = 1.0,
) -> Tensor:
    """Cross-entropy with an explicit, asymmetric cost for missed TB.

    DeepGB-TB applies a false-negative penalty (TRBL) and reports it worth
    about +0.2% AUROC. The reason to expose it here rather than hard-code it
    is that the penalty trades sensitivity against specificity directly, and
    which way to trade it is a deployment decision, not a modelling one. A
    triage tool that must not miss cases wants a value above 1; one that must
    not cry wolf wants it below 1.

    This does not resolve the WHO TPP inversion, where the target product
    profile asks for high sensitivity and lower specificity than a diagnostic
    test. See docs/RESEARCH_ROADMAP.md.
    """
    if false_negative_penalty <= 0.0:
        raise ValueError("false_negative_penalty must be positive")
    weights = class_weights
    if false_negative_penalty != 1.0:
        if weights is None:
            weights = torch.ones(2, dtype=logits.dtype, device=logits.device)
        else:
            weights = weights.clone()
        # Index 1 is the positive (TB) class; only its cost changes.
        weights[1] = weights[1] * float(false_negative_penalty)
    return torch.nn.functional.cross_entropy(logits, labels.long(), weight=weights)


def train_one_epoch(
    model: Module,
    optimizer: Optimizer,
    batches: Iterable[Batch],
    *,
    device: str | torch.device = "cpu",
    class_weights: Tensor | None = None,
    false_negative_penalty: float = 1.0,
    distillation_weight: float = 0.0,
) -> float:
    """Run one supervised epoch over patient-level batches."""
    model.to(device)
    model.train()
    total_loss = 0.0
    batch_count = 0
    for batch in batches:
        clips, clip_mask, metadata, labels, teacher_logits = _unpack_batch(batch)
        optimizer.zero_grad(set_to_none=True)
        logits = model(
            clips.to(device) if clips is not None else None,
            metadata.to(device) if metadata is not None else None,
            clip_mask=clip_mask.to(device) if clip_mask is not None else None,
        )
        loss = risk_balanced_loss(
            logits,
            labels.to(device),
            class_weights=class_weights.to(device) if class_weights is not None else None,
            false_negative_penalty=false_negative_penalty,
        )
        if distillation_weight > 0.0:
            if teacher_logits is None or clip_mask is None:
                raise ValueError(
                    "distillation_weight is set but the batch carries no teacher logits"
                )
            from src.pretrained_audio import distillation_loss

            # The teacher labels clips while this model labels patients, so the
            # clip opinions are pooled to one per patient to match shapes.
            mask = clip_mask.to(device)
            pooled = (
                (teacher_logits.to(device) * mask.unsqueeze(-1)).sum(dim=1)
                / mask.sum(dim=1, keepdim=True)
            )
            loss = loss + distillation_loss(
                logits, pooled, weight=distillation_weight
            )
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu().item())
        batch_count += 1

    if batch_count == 0:
        raise ValueError("at least one training batch is required")
    return total_loss / batch_count
