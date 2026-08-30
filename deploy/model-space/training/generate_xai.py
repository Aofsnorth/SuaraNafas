from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from torch.nn import Module

from src.audio_features import extract_log_mel
from src.model_runtime import load_torch_screening_model

CANVAS_SIZE = (1280, 720)
PLOT_ORIGIN = (90, 95)
PLOT_SIZE = (1100, 500)
COLORMAP_STOPS = (
    (0.0, (15, 23, 42)),
    (0.35, (14, 116, 144)),
    (0.65, (34, 197, 94)),
    (1.0, (250, 204, 21)),
)


def _probability(model: Module, features: np.ndarray) -> float:
    clips = torch.from_numpy(features).unsqueeze(0).unsqueeze(0)
    with torch.inference_mode():
        logits = model(clips, metadata=None)
        return float(torch.softmax(logits, dim=1)[0, 1].item())


def occlusion_sensitivity(
    model: Module,
    features: np.ndarray,
    *,
    frequency_patch: int = 16,
    time_patch: int = 4,
) -> tuple[np.ndarray, float]:
    """Measure TB-score change after zeroing local spectrogram patches."""
    baseline = _probability(model, features)
    heatmap = np.zeros(features.shape[1:], dtype=np.float32)
    counts = np.zeros_like(heatmap)
    for frequency in range(0, features.shape[1], frequency_patch):
        for frame in range(0, features.shape[2], time_patch):
            masked = features.copy()
            frequency_end = min(frequency + frequency_patch, features.shape[1])
            frame_end = min(frame + time_patch, features.shape[2])
            masked[:, frequency:frequency_end, frame:frame_end] = 0.0
            impact = abs(baseline - _probability(model, masked))
            heatmap[frequency:frequency_end, frame:frame_end] += impact
            counts[frequency:frequency_end, frame:frame_end] += 1.0
    sensitivity = heatmap / np.maximum(counts, 1.0)
    sensitivity /= float(sensitivity.max() + 1e-12)
    return sensitivity, baseline


def _colorize(values: np.ndarray) -> np.ndarray:
    rgb = np.zeros((*values.shape, 3), dtype=np.float32)
    for stop_index in range(len(COLORMAP_STOPS) - 1):
        low_value, low_color = COLORMAP_STOPS[stop_index]
        high_value, high_color = COLORMAP_STOPS[stop_index + 1]
        selected = (values >= low_value) & (values <= high_value)
        blend = np.clip(
            (values - low_value) / max(high_value - low_value, 1e-8),
            0.0,
            1.0,
        )
        for channel in range(3):
            rgb[..., channel][selected] = (
                low_color[channel]
                + blend[selected] * (high_color[channel] - low_color[channel])
            )
    return rgb.astype(np.uint8)


def render_visualization(
    features: np.ndarray,
    sensitivity: np.ndarray,
    probability: float,
    output_path: Path,
) -> None:
    spectrogram = _colorize(features[0])
    overlay = np.zeros_like(spectrogram)
    overlay[..., 0] = np.asarray(255 * sensitivity, dtype=np.uint8)
    overlay[..., 1] = np.asarray(90 * sensitivity, dtype=np.uint8)
    combined = np.asarray(0.72 * spectrogram + 0.28 * overlay, dtype=np.uint8)
    plot = Image.fromarray(combined).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    plot = plot.resize(PLOT_SIZE, Image.Resampling.NEAREST)

    canvas = Image.new("RGB", CANVAS_SIZE, (7, 15, 28))
    canvas.paste(plot, PLOT_ORIGIN)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=28)
    small_font = ImageFont.load_default(size=20)
    draw.text((90, 30), "From-scratch CNN — occlusion sensitivity", fill=(241, 245, 249), font=font)
    draw.text(
        (90, 620),
        f"Model TB score for this research sample: {probability:.3f}",
        fill=(226, 232, 240),
        font=small_font,
    )
    draw.text(
        (90, 655),
        "Brighter regions changed the model score more when occluded. Not a diagnosis.",
        fill=(148, 163, 184),
        font=small_font,
    )
    draw.text((40, 300), "Frequency", fill=(203, 213, 225), font=small_font)
    draw.text((575, 595), "Time", fill=(203, 213, 225), font=small_font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate XAI from a trained audio CNN")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    screening_model = load_torch_screening_model(
        args.manifest,
        allow_blocked_candidate=True,
    )
    feature_config = screening_model._feature_config
    model = screening_model._model
    features = extract_log_mel(args.audio.read_bytes(), feature_config)
    sensitivity, probability = occlusion_sensitivity(model, features)
    render_visualization(features, sensitivity, probability, args.output)
    print(f"saved XAI visualization: {args.output}")


if __name__ == "__main__":
    main()
