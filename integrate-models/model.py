from pathlib import Path
from typing import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import resnet18


class PrototypeLayer(nn.Module):
    def __init__(self, num_prototypes: int = 10, feature_depth: int = 256):
        super().__init__()
        self.num_prototypes = num_prototypes
        self.prototypes = nn.Parameter(
            torch.randn(num_prototypes, feature_depth, 1, 1)
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x_norm = F.normalize(x, p=2, dim=1)
        prototype_norm = F.normalize(self.prototypes, p=2, dim=1)
        distances = torch.sum(
            (x_norm.unsqueeze(1) - prototype_norm.unsqueeze(0)) ** 2,
            dim=2,
        )
        min_distances = distances.flatten(2).min(dim=2).values
        similarities = torch.exp(-min_distances)
        return similarities, min_distances


class PretrainedFeatureExtractor(nn.Module):
    def __init__(self):
        super().__init__()
        # weights=None prevents a network download during deployment. The
        # trained state dict replaces every retained weight immediately.
        backbone = resnet18(weights=None)
        self.features = nn.Sequential(
            backbone.conv1,
            backbone.bn1,
            backbone.relu,
            backbone.maxpool,
            backbone.layer1,
            backbone.layer2,
            backbone.layer3,
        )
        self.adaptive_pool = nn.AdaptiveAvgPool2d((8, 4))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.adaptive_pool(self.features(x.repeat(1, 3, 1, 1)))


class AttentionMIL(nn.Module):
    def __init__(self, feature_dim: int = 256, hidden_dim: int = 128):
        super().__init__()
        self.attention_V = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.Tanh(),
        )
        self.attention_U = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.Sigmoid(),
        )
        self.attention_w = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.softmax(
            self.attention_w(self.attention_V(x) * self.attention_U(x)),
            dim=0,
        )


class MultimodalSuaraNafasModel(nn.Module):
    def __init__(
        self,
        metadata_dim: int = 43,
        num_grid_cells: int = 16,
        num_prototypes: int = 10,
    ):
        super().__init__()
        self.num_grid_cells = num_grid_cells
        self.feature_extractor = PretrainedFeatureExtractor()
        self.yoho_pool = nn.AdaptiveAvgPool2d((4, 4))
        self.yoho_fc = nn.Sequential(
            nn.Linear(256 * 4 * 4, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_grid_cells * 3),
        )
        self.proto_layer = PrototypeLayer(num_prototypes, 256)
        self.clip_attention = AttentionMIL(256, 128)
        self.meta_fc = nn.Sequential(
            nn.BatchNorm1d(metadata_dim),
            nn.Linear(metadata_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 32),
            nn.ReLU(),
        )
        self.global_classifier = nn.Sequential(
            nn.Linear(num_prototypes + 32, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 2),
        )

    def forward(
        self,
        specs: Sequence[torch.Tensor],
        metadata: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        model_device = next(self.parameters()).device
        metadata = metadata.to(model_device)
        patient_similarities = []
        patient_yoho_outputs = []
        patient_min_distances = []

        for patient_clips in specs:
            patient_clips = patient_clips.to(model_device)
            conv_features = self.feature_extractor(patient_clips)
            clip_embeddings = F.adaptive_avg_pool2d(
                conv_features, 1
            ).flatten(1)
            attention = self.clip_attention(clip_embeddings)

            yoho_features = self.yoho_pool(conv_features).flatten(1)
            yoho_output = torch.sigmoid(
                self.yoho_fc(yoho_features).view(
                    -1, self.num_grid_cells, 3
                )
            )
            patient_yoho_outputs.append(
                (attention.unsqueeze(-1) * yoho_output).sum(dim=0)
            )

            similarities, min_distances = self.proto_layer(conv_features)
            patient_similarities.append(
                (attention * similarities).sum(dim=0)
            )
            patient_min_distances.append(
                (attention * min_distances).sum(dim=0)
            )

        prototype_features = torch.stack(patient_similarities)
        metadata_features = self.meta_fc(metadata)
        logits = self.global_classifier(
            torch.cat((prototype_features, metadata_features), dim=1)
        )

        return {
            "yoho_outputs": torch.stack(patient_yoho_outputs),
            "tb_logits": logits,
            "proto_similarities": prototype_features,
            "min_distances": torch.stack(patient_min_distances),
        }


def load_model(
    weights_path: str | Path = "tb_cough_edge_weights_fp32.pt",
    device: str | torch.device = "cpu",
) -> MultimodalSuaraNafasModel:
    device = torch.device(device)
    model = MultimodalSuaraNafasModel(metadata_dim=43)
    state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    return model.to(device).eval()


@torch.inference_mode()
def predict_tb_risk(
    model: MultimodalSuaraNafasModel,
    patient_specs: torch.Tensor,
    metadata: torch.Tensor,
) -> float:
    if patient_specs.ndim != 4 or patient_specs.shape[1:] != (1, 128, 36):
        raise ValueError("patient_specs must have shape (clips, 1, 128, 36)")
    if metadata.shape != (1, 43):
        raise ValueError("metadata must have shape (1, 43)")

    logits = model([patient_specs], metadata)["tb_logits"]
    return F.softmax(logits, dim=1)[0, 1].item()
