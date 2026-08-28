from __future__ import annotations

import torch

from src.model import SpectrogramClinicalClassifier
from training.runner import train_one_epoch


def test_train_one_epoch_updates_model_parameters() -> None:
    model = SpectrogramClinicalClassifier(metadata_dim=27, input_mode="fusion")
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    clips = torch.randn(4, 2, 1, 128, 36)
    metadata = torch.randn(4, 27)
    labels = torch.tensor([0, 1, 0, 1])
    before = [parameter.detach().clone() for parameter in model.parameters()]

    loss = train_one_epoch(model, optimizer, [(clips, metadata, labels)])

    assert loss > 0.0
    assert any(
        not torch.equal(previous, current)
        for previous, current in zip(before, model.parameters())
    )
