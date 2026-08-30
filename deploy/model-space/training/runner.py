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


def _unpack_batch(batch: Batch) -> tuple[Tensor | None, Tensor | None, Tensor | None, Tensor]:
    if len(batch) == 3:
        clips, metadata, labels = batch
        return clips, None, metadata, labels
    clips, clip_mask, metadata, labels = batch
    return clips, clip_mask, metadata, labels


def train_patient_equal_clip_epoch(
    model: ResidualSpectrogramClassifier,
    optimizer: Optimizer,
    batches: Iterable[Batch],
    *,
    device: str | torch.device = "cpu",
    class_weights: Tensor | None = None,
) -> float:
    """Train on clips while assigning equal total loss weight to each patient."""
    model.to(device).train()
    total_loss = 0.0
    batch_count = 0
    for batch in batches:
        clips, clip_mask, _, labels = _unpack_batch(batch)
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
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu().item())
        batch_count += 1

    if batch_count == 0:
        raise ValueError("at least one training batch is required")
    return total_loss / batch_count


def train_one_epoch(
    model: Module,
    optimizer: Optimizer,
    batches: Iterable[Batch],
    *,
    device: str | torch.device = "cpu",
    class_weights: Tensor | None = None,
) -> float:
    """Run one supervised epoch over patient-level batches."""
    model.to(device)
    model.train()
    total_loss = 0.0
    batch_count = 0
    for batch in batches:
        clips, clip_mask, metadata, labels = _unpack_batch(batch)
        optimizer.zero_grad(set_to_none=True)
        logits = model(
            clips.to(device) if clips is not None else None,
            metadata.to(device) if metadata is not None else None,
            clip_mask=clip_mask.to(device) if clip_mask is not None else None,
        )
        loss = torch.nn.functional.cross_entropy(
            logits,
            labels.to(device).long(),
            weight=class_weights.to(device) if class_weights is not None else None,
        )
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach().cpu().item())
        batch_count += 1

    if batch_count == 0:
        raise ValueError("at least one training batch is required")
    return total_loss / batch_count
