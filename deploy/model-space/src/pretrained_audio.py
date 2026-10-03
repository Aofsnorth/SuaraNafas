"""Optional pretrained audio teacher for knowledge distillation.

Why this exists
---------------
The deployed residual student is randomly initialised by design: it is small
(about 313k parameters, roughly 1.2 MB on disk) and loads in a Hugging Face
Space on CPU. That constraint is also the reason its cross-validated AUROC is
low — it learns from ~1105 participants with no prior knowledge of what a cough
sounds like. Published comparisons on this task consistently show that reusing a
general-audio encoder beats training the same backbone from scratch, and that
pre-training also shrinks the variance across evaluation folds.

A *frozen teacher* is the way to take that benefit without giving up the small
artifact: the teacher only shapes the student's gradients during training and
is thrown away afterwards, so ``pretrained_weights`` stays ``False`` in the
manifest and the shipped model is unchanged in size.

Teacher choice
--------------
``facebook/ast-finetuned-audioset-10-10-0.97`` is the default because it ships
inside ``transformers`` with a numpy-only front end, so no ``torchaudio``
install is required. It was fine-tuned on AudioSet, which has no tuberculosis
class, so encoding clips cannot leak the label.

This module is entirely optional. Nothing in the training or serving path
imports it unless distillation is explicitly requested.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_TEACHER_ID = "facebook/ast-finetuned-audioset-10-10-0.97"


@dataclass(frozen=True)
class TeacherConfig:
    """Settings for the frozen teacher and the distillation objective."""

    model_id: str = DEFAULT_TEACHER_ID
    sample_rate: int = 16000
    max_seconds: float = 10.24
    batch_size: int = 16
    temperature: float = 2.0
    weight: float = 0.3

    def __post_init__(self) -> None:
        if not 0.0 < self.weight < 1.0:
            raise ValueError("distillation weight must be strictly between 0 and 1")
        if self.temperature <= 0:
            raise ValueError("distillation temperature must be positive")
        if self.max_seconds <= 0 or self.batch_size < 1:
            raise ValueError("max_seconds must be positive and batch_size at least 1")


def _waveform_to_mono_16k(audio: np.ndarray, sample_rate: int, config: TeacherConfig) -> np.ndarray:
    """Resample and truncate to the front end the teacher expects.

    Uses a plain linear resampler so ``torchaudio``/``scipy`` stay optional.
    Teacher embeddings are a weak auxiliary signal, so a plain resampler is
    adequate; the ground truth still comes from the full-resolution spectrogram
    path in ``src.audio_features``.
    """
    if audio.ndim > 1:
        audio = audio.mean(axis=1 if audio.shape[0] < audio.shape[-1] else -1)
    if sample_rate != config.sample_rate:
        duration = audio.shape[0] / float(sample_rate)
        target_length = max(1, int(round(duration * config.sample_rate)))
        source_positions = np.linspace(0.0, audio.shape[0] - 1, num=target_length)
        audio = np.interp(source_positions, np.arange(audio.shape[0]), audio).astype(np.float32)
    target_length = int(round(config.max_seconds * config.sample_rate))
    if audio.shape[0] < target_length:
        audio = np.pad(audio, (0, target_length - audio.shape[0]))
    return np.asarray(audio[:target_length], dtype=np.float32)


class TeacherEmbedder:
    """Frozen AST teacher producing one pooled embedding per clip.

    The teacher runs where the student trains. Leaving it on CPU made an
    embedding pass dominate the whole run while the GPU sat idle.
    """

    def __init__(
        self, config: TeacherConfig | None = None, *, device: str | None = None
    ) -> None:
        self.config = config or TeacherConfig()
        self.device = device
        self._model: Any | None = None
        self._extractor: Any | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import ASTFeatureExtractor, ASTModel
        except ImportError as error:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "distillation requires `pip install transformers`. The training "
                "and serving paths do not need it, so install it only in the "
                "training environment."
            ) from error
        import torch

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._extractor = ASTFeatureExtractor.from_pretrained(self.config.model_id)
        self._model = ASTModel.from_pretrained(self.config.model_id).to(self.device)
        self._model.eval()
        for parameter in self._model.parameters():
            parameter.requires_grad_(False)

    @property
    def embedding_dim(self) -> int:
        self._ensure_loaded()
        return int(self._model.config.hidden_size)

    def embed_waveforms(
        self,
        waveforms: Sequence[np.ndarray],
        *,
        sample_rate: int,
    ) -> np.ndarray:
        """Return one pooled teacher embedding per supplied waveform."""
        if not waveforms:
            raise ValueError("at least one waveform is required")
        self._ensure_loaded()
        import torch

        prepared = [
            _waveform_to_mono_16k(np.asarray(waveform, dtype=np.float32), sample_rate, self.config)
            for waveform in waveforms
        ]
        outputs: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, len(prepared), self.config.batch_size):
                chunk = prepared[start : start + self.config.batch_size]
                features = self._extractor(
                    chunk,
                    sampling_rate=self.config.sample_rate,
                    return_tensors="pt",
                )
                features = {key: value.to(self.device) for key, value in features.items()}
                hidden = self._model(**features).last_hidden_state
                pooled = hidden.mean(dim=1)
                outputs.append(pooled.detach().cpu().numpy().astype(np.float32))
        return np.concatenate(outputs, axis=0)


class TeacherEmbeddingCache:
    """Content-addressed on-disk cache of teacher embeddings.

    Encoding tens of thousands of clips through AST is far slower than the
    student training itself, so embeddings are computed once and reused. The
    cache is keyed by the teacher identity *and* the audio bytes, which keeps
    stale entries from a different teacher or edited audio out of the picture.
    """

    def __init__(self, path: str | Path, *, model_id: str = DEFAULT_TEACHER_ID) -> None:
        self.path = Path(path)
        self.model_id = model_id
        self._index: dict[str, int] = {}
        self._vectors: list[np.ndarray] = []
        if self.path.is_file():
            self._load()

    @staticmethod
    def key_for(audio_bytes: bytes, model_id: str) -> str:
        digest = hashlib.sha256()
        digest.update(model_id.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(audio_bytes)
        return digest.hexdigest()

    def _load(self) -> None:
        data = np.load(self.path, allow_pickle=False)
        self._vectors = [row for row in data["embeddings"]]
        self._index = {str(key): int(row) for row, key in enumerate(data["keys"])}

    def get(self, key: str) -> np.ndarray | None:
        position = self._index.get(key)
        return None if position is None else self._vectors[position]

    def put(self, key: str, vector: np.ndarray) -> None:
        if key in self._index:
            self._vectors[self._index[key]] = np.asarray(vector, dtype=np.float32)
            return
        self._index[key] = len(self._vectors)
        self._vectors.append(np.asarray(vector, dtype=np.float32))

    def flush(self) -> Path:
        if not self._vectors:
            raise ValueError("refusing to write an empty teacher cache")
        width = len(self._vectors[0])
        if any(len(vector) != width for vector in self._vectors):
            raise ValueError("teacher embeddings have inconsistent dimensions")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.path,
            embeddings=np.stack(self._vectors).astype(np.float32),
            keys=np.asarray(list(self._index), dtype="U64"),
            model_id=np.asarray(self.model_id),
        )
        return self.path

    @property
    def dim(self) -> int:
        return len(self._vectors[0]) if self._vectors else 0

    @property
    def size(self) -> int:
        return len(self._vectors)


def embed_clips(
    paths: Sequence[Path],
    cache: TeacherEmbeddingCache,
    embedder: TeacherEmbedder,
    *,
    sample_rate: int,
) -> np.ndarray:
    """Embed clips, computing only those the cache does not already hold."""
    keys = [cache.key_for(path.read_bytes(), cache.model_id) for path in paths]
    missing = [index for index, key in enumerate(keys) if cache.get(key) is None]
    if missing:
        batch = [paths[index] for index in missing]
        vectors = embedder.embed_waveforms(
            [_read_waveform(path) for path in batch], sample_rate=sample_rate
        )
        for index, vector in zip(missing, vectors, strict=True):
            cache.put(keys[index], vector)
    cached = [cache.get(key) for key in keys]
    if any(vector is None for vector in cached):
        raise RuntimeError("teacher cache lookup failed after embedding")
    return np.stack(cached).astype(np.float32)


def _read_waveform(path: Path) -> np.ndarray:
    """Read a PCM WAV file without requiring soundfile or torchaudio."""
    import wave

    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise ValueError(f"{path.name} is not 16-bit PCM")
        frames = handle.readframes(handle.getnframes())
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if handle.getnchannels() > 1:
        audio = audio.reshape(-1, handle.getnchannels()).mean(axis=1)
    return audio


def distillation_loss(
    student_logits: Any,
    teacher_logits: Any,
    *,
    weight: float,
    temperature: float = 2.0,
) -> Any:
    """Temperature-scaled KL divergence from teacher to student.

    The student is additionally trained on the hard labels, so this term only
    supplies a smoother gradient on the rare positive class. ``weight`` should
    stay well below 1.0 to avoid teaching the student the teacher's own
    biases.
    """
    import torch

    if not 0.0 < weight < 1.0:
        raise ValueError("distillation weight must be strictly between 0 and 1")
    if temperature <= 0:
        raise ValueError("distillation temperature must be positive")
    if student_logits.shape != teacher_logits.shape:
        raise ValueError(
            "student and teacher logits must match; the teacher head must be "
            f"projected to the student's class count, got {student_logits.shape} "
            f"and {teacher_logits.shape}"
        )
    # Detach defensively: the teacher is frozen, so no gradient may reach it
    # even if a caller forgets to disable grad on the teacher module.
    teacher_logits = teacher_logits.detach()
    student_log_probs = torch.log_softmax(student_logits / temperature, dim=1)
    teacher_log_probs = torch.log_softmax(teacher_logits / temperature, dim=1)
    teacher_probs = teacher_log_probs.exp()
    # KL(teacher || student) = sum_i P_i (log P_i - log Q_i). Using the
    # cross-entropy form -(P log Q) instead would add the teacher's entropy,
    # which is a constant in the student but makes the reported loss nonzero
    # even when the two models already agree exactly.
    per_sample = (teacher_probs * (teacher_log_probs - student_log_probs)).sum(dim=1).mean()
    return weight * (temperature**2) * per_sample


def fit_teacher_probe(
    embeddings: Any,
    labels: Any,
    *,
    hidden_dim: int = 768,
    classes: int = 2,
    epochs: int = 60,
    learning_rate: float = 1e-2,
) -> tuple[Any, Any]:
    """Fit a linear 768->classes probe and return (probe, teacher_logits).

    This is deliberately the weakest possible use of a pretrained teacher: a
    single linear layer read out of frozen AST embeddings. Anything richer
    would be a second model rather than a teacher.

    The probe is fitted on the *training* partition only and must be asked for
    logits on the same partition. Those logits are therefore in-sample: they
    describe how a linear readout of a frozen AudioSet encoder sees the training
    clips, not an independent opinion. Callers must not fit on held-out data.
    """
    import torch

    x = torch.as_tensor(embeddings, dtype=torch.float32)
    y = torch.as_tensor(labels, dtype=torch.long)
    if x.ndim != 2 or x.shape[0] != y.shape[0]:
        raise ValueError("embeddings must be (clips, dim) and match the label count")
    if int(torch.unique(y).numel()) < 2:
        raise ValueError("the teacher probe needs at least two classes")

    probe = torch.nn.Linear(hidden_dim, classes)
    torch.nn.init.zeros_(probe.bias)
    optimizer = torch.optim.Adam(probe.parameters(), lr=learning_rate)
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        torch.nn.functional.cross_entropy(probe(x), y).backward()
        optimizer.step()
    probe.eval()
    for parameter in probe.parameters():
        parameter.requires_grad_(False)
    with torch.inference_mode():
        teacher_logits = probe(x).detach().cpu().numpy().astype("float32")
    return probe, teacher_logits
