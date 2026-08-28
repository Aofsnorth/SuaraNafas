from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

import torch
from torch import Tensor
from torch.nn import Module
from torch.optim import Optimizer


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
