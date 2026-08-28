from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias

import torch
from torch import Tensor
from torch.nn import Module

from training.metrics import calculate_binary_metrics


Batch: TypeAlias = (
    tuple[Tensor | None, Tensor | None, Tensor]
    | tuple[Tensor, Tensor, Tensor, Tensor]
)


@dataclass(frozen=True)
class EvaluationResult:
    labels: tuple[int, ...]
    probabilities: tuple[float, ...]
    metrics: dict[str, float | int | None]


def _unpack_batch(batch: Batch) -> tuple[Tensor | None, Tensor | None, Tensor | None, Tensor]:
    if len(batch) == 3:
        clips, metadata, labels = batch
        return clips, None, metadata, labels
    clips, clip_mask, metadata, labels = batch
    return clips, clip_mask, metadata, labels


def evaluate_model(
    model: Module,
    batches: Iterable[Batch],
    *,
    device: str | torch.device = "cpu",
) -> EvaluationResult:
    """Evaluate once at patient level; never tune thresholds here."""
    model.to(device).eval()
    labels: list[int] = []
    probabilities: list[float] = []
    with torch.inference_mode():
        for batch in batches:
            clips, clip_mask, metadata, batch_labels = _unpack_batch(batch)
            logits = model(
                clips.to(device) if clips is not None else None,
                metadata.to(device) if metadata is not None else None,
                clip_mask=clip_mask.to(device) if clip_mask is not None else None,
            )
            batch_probabilities = torch.softmax(logits, dim=1)[:, 1]
            labels.extend(int(label) for label in batch_labels.cpu().tolist())
            probabilities.extend(float(probability) for probability in batch_probabilities.cpu().tolist())
    metrics = calculate_binary_metrics(labels, probabilities)
    return EvaluationResult(tuple(labels), tuple(probabilities), metrics)
