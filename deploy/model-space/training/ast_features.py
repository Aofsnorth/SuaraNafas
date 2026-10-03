"""Pinned, frozen AudioSet AST features; no downloads occur at module import."""
from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import tempfile
import time
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import numpy as np

try:
    from src.audio_features import decode_wav
except ImportError:
    # Older model-space checkouts expose the same decoder only privately.
    from src.audio_features import _decode_pcm_wav as decode_wav
from training.dataset import PatientExample


MODEL_ID = "MIT/ast-finetuned-audioset-10-10-0.4593"
REVISION = "f826b80d28226b62986cc218e5cec390b1096902"
PREPROCESSING_ID = "ast-mono-polyphase-16k-energy-10.24s-extractor-defaults-pooler-mean-v1"
SAMPLE_RATE = 16_000
MAX_SAMPLES = 163_840
EMBEDDING_DIM = 768
SNAPSHOT_FILES = ("config.json", "preprocessor_config.json", "model.safetensors")


@dataclass(frozen=True)
class ASTConfig:
    model_id: str = MODEL_ID
    revision: str = REVISION
    batch_size: int = 4
    device: str = "cuda"

    def __post_init__(self) -> None:
        if self.model_id != MODEL_ID or self.revision != REVISION:
            raise ValueError("AST requires the pinned official AudioSet model and revision")
        if type(self.batch_size) is not int or self.batch_size < 1:
            raise ValueError("AST batch_size must be a positive integer")
        if not isinstance(self.device, str) or not (
            self.device in ("cpu", "cuda")
            or self.device.startswith("cuda:") and self.device[5:].isdigit()
        ):
            raise ValueError("AST device must be 'cuda', 'cuda:N', or explicit 'cpu'")


def local_model_dir(output_dir: Path, config: ASTConfig) -> Path:
    """Durable snapshot directory containing model.safetensors for later inference."""
    return Path(output_dir) / "ast_model" / config.revision


def prepare_waveform(audio_bytes: bytes) -> np.ndarray:
    """Decode mono float32 at 16 kHz, retaining at most the loudest 10.24 s.

    Short recordings are not stretched or padded here: the official extractor
    pads its filter-bank frames using its original configuration.
    """
    if not isinstance(audio_bytes, bytes) or not audio_bytes:
        raise ValueError("AST audio must contain non-empty WAV bytes")
    try:
        samples, source_rate = decode_wav(audio_bytes)
    except (ValueError, EOFError, OSError, struct.error) as error:
        raise ValueError(f"AST could not decode WAV audio: {error}") from error
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise ValueError("AST decoded audio must be non-empty, finite, and mono")
    if not isinstance(source_rate, (int, np.integer)) or source_rate < 1:
        raise ValueError("AST audio sample rate must be a positive integer")
    if source_rate != SAMPLE_RATE:
        try:
            from scipy.signal import resample_poly
        except ImportError as error:
            raise ValueError("AST audio requires scipy.signal.resample_poly for anti-aliased resampling") from error

        divisor = math.gcd(int(source_rate), SAMPLE_RATE)
        samples = resample_poly(samples, SAMPLE_RATE // divisor, int(source_rate) // divisor)
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise ValueError("AST resampled audio must be non-empty, mono, and contain no nonfinite samples")
    if samples.size > MAX_SAMPLES:
        energy = np.concatenate(([0.0], np.cumsum(samples.astype(np.float64) ** 2)))
        start = int(np.argmax(energy[MAX_SAMPLES:] - energy[:-MAX_SAMPLES]))
        samples = samples[start : start + MAX_SAMPLES]
    return np.ascontiguousarray(samples, dtype=np.float32)


class FrozenASTEncoder:
    """Official AST pooler embeddings (mean of CLS/distillation tokens).

    Construction requires CUDA by default, even before downloading. CPU is an
    explicit opt-in. A verified local snapshot can be reused entirely offline.
    """

    def __init__(self, config: ASTConfig, model_dir: Path) -> None:
        import torch

        self.config = config
        self.model_dir = Path(model_dir)
        self._torch = torch
        self.device = torch.device(config.device)
        if self.device.type == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("AST requires CUDA; no CPU fallback (use device='cpu' explicitly)")
            if self.device.index is not None and self.device.index >= torch.cuda.device_count():
                raise ValueError(f"AST CUDA device is unavailable: {config.device}")
        _ensure_snapshot(self.model_dir, config)
        from transformers import ASTFeatureExtractor, ASTModel

        self.extractor = ASTFeatureExtractor.from_pretrained(
            str(self.model_dir), local_files_only=True, trust_remote_code=False,
        )
        self.model = ASTModel.from_pretrained(
            str(self.model_dir), local_files_only=True,
            use_safetensors=True, trust_remote_code=False,
        )
        self.model.to(self.device)
        self.model.eval()
        self.model.requires_grad_(False)

    @staticmethod
    def prepare_waveform(audio_bytes: bytes) -> np.ndarray:
        return prepare_waveform(audio_bytes)

    def embed_paths(self, paths: Sequence[Path]) -> np.ndarray:
        """Return (len(paths), 768) float32 features in the exact input order."""
        if not paths:
            raise ValueError("AST embed_paths requires at least one audio path")
        started = time.monotonic()
        batches = []
        for start in range(0, len(paths), self.config.batch_size):
            selected = paths[start : start + self.config.batch_size]
            waveforms = [self.prepare_waveform(_read_audio(Path(path))) for path in selected]
            batches.append(self._embed_waveforms(waveforms))
            self._report_batch(start + len(selected), len(paths), started)
        return np.concatenate(batches, axis=0)

    def embed_bytes(self, clips: Sequence[bytes]) -> np.ndarray:
        """Encode the exact bytes hashed by the cache, with one decode per clip."""
        if not clips:
            raise ValueError("AST embed_bytes requires at least one audio clip")
        started = time.monotonic()
        batches = []
        for start in range(0, len(clips), self.config.batch_size):
            selected = clips[start : start + self.config.batch_size]
            waveforms = [self.prepare_waveform(audio) for audio in selected]
            batches.append(self._embed_waveforms(waveforms))
            self._report_batch(start + len(selected), len(clips), started)
        return np.concatenate(batches, axis=0)

    def _embed_waveforms(self, waveforms: Sequence[np.ndarray]) -> np.ndarray:
        # Kaldi's 25-ms fbank window cannot process shorter recordings, even
        # though the extractor subsequently pads the number of feature frames.
        if any(waveform.size < 400 for waveform in waveforms):
            raise ValueError("AST audio must contain at least 25 ms (400 samples at 16 kHz)")
        with self._torch.inference_mode():
            inputs = self.extractor(waveforms, sampling_rate=SAMPLE_RATE, return_tensors="pt")
            if not np.isfinite(inputs["input_values"].detach().cpu().numpy()).all():
                raise ValueError("AST extractor returned nonfinite input features")
            inputs = {name: tensor.to(self.device) for name, tensor in inputs.items()}
            pooled = self.model(**inputs).pooler_output
            if pooled is None:
                raise ValueError("AST model did not return pooler_output")
            embeddings = pooled.detach().cpu().numpy()
        return _validate_embeddings(embeddings, len(waveforms))

    def _report_batch(self, completed: int, total: int, started: float) -> None:
        if self.device.type == "cuda":
            gpu = self._torch.cuda.get_device_name(self.device)
            memory = self._torch.cuda.memory_allocated(self.device) / 2**20
            info = f"GPU={gpu} allocated={memory:.0f}MiB"
        else:
            info = "GPU=disabled (explicit CPU)"
        print(
            f"[AST] clips={completed}/{total} elapsed={time.monotonic() - started:.1f}s "
            f"device={self.device} {info}", flush=True,
        )


def extract_patient_embeddings(
    examples: Sequence[PatientExample], output_dir: Path, config: ASTConfig,
) -> np.ndarray:
    """Equally average selected clips; rows follow examples, including cache hits.

    The cache is independent of patient identifiers, labels and filenames. Its
    key covers source-byte hashes, pinned encoder identity and preprocessing.
    All-cache-hit calls need neither the model nor CUDA; no inference occurs.
    """
    if not examples:
        raise ValueError("AST requires at least one patient example")
    cache_dir = Path(output_dir) / "ast_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    encoder = None
    rows = []
    hits = 0
    started = time.monotonic()
    for index, example in enumerate(examples):
        if not example.audio_paths:
            raise ValueError(f"AST patient at index {index} has no selected audio clips")
        clips = [_read_audio(Path(path)) for path in example.audio_paths]
        key = _patient_cache_key(clips, config)
        cache_path = cache_dir / f"{key}.npz"
        if cache_path.is_file():
            embedding = _load_cached_embedding(cache_path, key)
            hits += 1
        else:
            if encoder is None:
                encoder = FrozenASTEncoder(config, local_model_dir(output_dir, config))
            features = _validate_embeddings(encoder.embed_bytes(clips), len(clips))
            embedding = features.mean(axis=0, dtype=np.float64).astype(np.float32)
            _atomic_write(cache_path, lambda stream: np.savez_compressed(
                stream, embedding=embedding, cache_key=np.asarray(key),
            ))
        rows.append(embedding)
        if (index + 1) % 20 == 0 or index + 1 == len(examples):
            gpu = "not initialized (cache only)" if encoder is None else config.device
            print(
                f"[AST] subjects={index + 1}/{len(examples)} cache_hits={hits} "
                f"elapsed={time.monotonic() - started:.1f}s GPU={gpu}", flush=True,
            )
    return _validate_embeddings(np.stack(rows), len(examples))


def _read_audio(path: Path) -> bytes:
    try:
        audio = path.read_bytes()
    except OSError as error:
        raise ValueError(f"AST could not read audio file: {path}") from error
    if not audio:
        raise ValueError(f"AST audio file is empty: {path}")
    return audio


def _patient_cache_key(clips: Sequence[bytes], config: ASTConfig) -> str:
    provenance = {
        "model_id": config.model_id, "revision": config.revision,
        "preprocessing_id": PREPROCESSING_ID,
        "audio_sha256": [hashlib.sha256(audio).hexdigest() for audio in clips],
    }
    return hashlib.sha256(json.dumps(provenance, sort_keys=True).encode("utf-8")).hexdigest()


def _validate_embeddings(embeddings: np.ndarray, rows: int) -> np.ndarray:
    array = np.asarray(embeddings)
    if array.shape != (rows, EMBEDDING_DIM) or array.dtype.kind not in "fiu":
        raise ValueError(f"AST embeddings must be numeric with shape ({rows}, {EMBEDDING_DIM})")
    with np.errstate(over="ignore", invalid="ignore"):
        array = array.astype(np.float32, copy=False)
    if not np.isfinite(array).all():
        raise ValueError("AST embeddings contain nonfinite values")
    return array


def _load_cached_embedding(path: Path, key: str) -> np.ndarray:
    try:
        with np.load(path, allow_pickle=False) as cache:
            if cache["cache_key"].item() != key:
                raise ValueError("content hash does not match cache key")
            embedding = cache["embedding"]
            if embedding.shape != (EMBEDDING_DIM,):
                raise ValueError("patient embedding has invalid shape")
            return _validate_embeddings(embedding[None, :], 1)[0]
    except (ValueError, TypeError, KeyError, OSError, EOFError, zipfile.BadZipFile) as error:
        raise ValueError(f"Invalid AST cache {path.name}; remove it to recompute: {error}") from error


def _ensure_snapshot(model_dir: Path, config: ASTConfig) -> None:
    manifest_path = model_dir / "ast_provenance.json"
    if manifest_path.is_file():
        _verify_snapshot(model_dir, config)
        return
    from huggingface_hub import snapshot_download

    model_dir.mkdir(parents=True, exist_ok=True)
    # No pickle weights, Python code, or files from a mutable branch are fetched.
    snapshot_download(
        repo_id=config.model_id, revision=config.revision, repo_type="model",
        local_dir=str(model_dir), allow_patterns=list(SNAPSHOT_FILES),
        force_download=True,
    )
    manifest = {
        "model_id": config.model_id, "revision": config.revision,
        "preprocessing_id": PREPROCESSING_ID, "sha256": _snapshot_hashes(model_dir),
    }
    payload = json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8")
    _atomic_write(manifest_path, lambda stream: stream.write(payload))


def _snapshot_hashes(model_dir: Path) -> dict[str, str]:
    hashes = {}
    for filename in SNAPSHOT_FILES:
        path = model_dir / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"AST snapshot requires a durable local file: {filename}")
        with path.open("rb") as stream:
            hashes[filename] = hashlib.file_digest(stream, "sha256").hexdigest()
    return hashes


def _verify_snapshot(model_dir: Path, config: ASTConfig) -> None:
    try:
        manifest = json.loads((model_dir / "ast_provenance.json").read_text(encoding="utf-8"))
        expected = {
            "model_id": config.model_id, "revision": config.revision,
            "preprocessing_id": PREPROCESSING_ID, "sha256": _snapshot_hashes(model_dir),
        }
        if manifest != expected:
            raise ValueError("pinned identity, preprocessing or file hashes do not match")
    except (ValueError, OSError) as error:
        raise ValueError(f"Invalid AST local snapshot: {error}") from error


def _atomic_write(path: Path, write: Callable[[BinaryIO], object]) -> None:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
