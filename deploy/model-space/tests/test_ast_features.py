from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
import types
import unittest
import wave
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from training import ast_features as ast
from training.dataset import PatientExample


HAS_SCIPY = importlib.util.find_spec("scipy") is not None


def wav_bytes(samples: np.ndarray, sample_rate: int = 16_000) -> bytes:
    samples = np.asarray(samples)
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(samples.shape[1] if samples.ndim == 2 else 1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes((samples * 32767).astype("<i2").tobytes())
        return buffer.getvalue()


def patient(*paths: Path, patient_id: str = "patient") -> PatientExample:
    return PatientExample(patient_id, 0, tuple(paths), {})


class FakeEncoder:
    instances: list[FakeEncoder] = []

    def __init__(self, config: ast.ASTConfig, model_dir: Path) -> None:
        self.config = config
        self.model_dir = model_dir
        self.calls: list[list[bytes]] = []
        self.instances.append(self)

    def embed_bytes(self, clips: list[bytes]) -> np.ndarray:
        self.calls.append(list(clips))
        return np.stack([
            np.full(ast.EMBEDDING_DIM, float(audio.decode("ascii")), dtype=np.float32)
            for audio in clips
        ])


class WaveformTests(unittest.TestCase):
    def test_stereo_is_averaged_to_mono_without_manual_padding(self) -> None:
        stereo = np.tile([0.6, -0.2], (4000, 1))
        waveform = ast.prepare_waveform(wav_bytes(stereo))
        self.assertEqual(waveform.shape, (4000,))
        self.assertEqual(waveform.dtype, np.float32)
        np.testing.assert_allclose(waveform, 0.2, atol=1e-4)

    @unittest.skipUnless(HAS_SCIPY, "scipy is required for real polyphase resampling")
    def test_resampling_preserves_duration_and_mono(self) -> None:
        for rate in (8000, 22050, 44100, 48000):
            with self.subTest(rate=rate):
                time_axis = np.arange(rate // 2) / rate
                tone = 0.4 * np.sin(2 * np.pi * 440 * time_axis)
                waveform = ast.prepare_waveform(wav_bytes(np.column_stack([tone, tone]), rate))
                self.assertLessEqual(abs(waveform.size / 16000 - tone.size / rate), 1 / 16000)
                self.assertEqual(waveform.ndim, 1)
                self.assertTrue(np.isfinite(waveform).all())

    @unittest.skipUnless(HAS_SCIPY, "scipy is required to verify anti-aliasing")
    def test_downsampling_suppresses_above_nyquist_energy(self) -> None:
        time_axis = np.arange(48000) / 48000
        tone = 0.5 * np.sin(2 * np.pi * 12000 * time_axis)
        waveform = ast.prepare_waveform(wav_bytes(tone, 48000))
        self.assertLess(float(np.sqrt(np.mean(waveform[100:-100] ** 2))), 0.01)

    def test_polyphase_uses_reduced_integer_ratio(self) -> None:
        signal = types.ModuleType("scipy.signal")
        expected = np.ones(16000, dtype=np.float32)
        calls = []

        def resample(samples: np.ndarray, up: int, down: int) -> np.ndarray:
            calls.append((samples.size, up, down))
            return expected

        signal.resample_poly = resample
        scipy = types.ModuleType("scipy")
        scipy.signal = signal
        with patch.dict("sys.modules", {"scipy": scipy, "scipy.signal": signal}):
            actual = ast.prepare_waveform(wav_bytes(np.ones(44100) * 0.2, 44100))
        self.assertEqual(calls, [(44100, 160, 441)])
        np.testing.assert_array_equal(actual, expected)

    def test_long_input_selects_highest_energy_window_including_tail(self) -> None:
        samples = np.concatenate((np.zeros(16000), np.full(ast.MAX_SAMPLES, 0.4)))
        actual = ast.prepare_waveform(wav_bytes(samples))
        self.assertEqual(actual.shape, (ast.MAX_SAMPLES,))
        np.testing.assert_allclose(actual, 0.4, atol=1e-4)

    def test_empty_invalid_and_nonfinite_audio_raise_value_error(self) -> None:
        for payload in (b"", b"not WAV", wav_bytes(np.zeros(0)), wav_bytes(np.ones(400))[:-1]):
            with self.subTest(payload=payload[:10]):
                with self.assertRaises(ValueError):
                    ast.prepare_waveform(payload)
        for samples in (np.array([np.nan]), np.array([np.inf]), np.zeros((2, 2))):
            with patch.object(ast, "decode_wav", return_value=(samples, 16000)):
                with self.assertRaisesRegex(ValueError, "finite.*mono"):
                    ast.prepare_waveform(b"audio")

    def test_nonfinite_resampling_raises_value_error(self) -> None:
        signal = types.ModuleType("scipy.signal")
        signal.resample_poly = lambda *args: np.array([np.nan])
        with patch.dict("sys.modules", {"scipy.signal": signal}):
            with self.assertRaisesRegex(ValueError, "resampled.*nonfinite"):
                ast.prepare_waveform(wav_bytes(np.ones(800), 8000))


class PatientCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.config = ast.ASTConfig()
        FakeEncoder.instances = []
        self.encoder_patch = patch.object(ast, "FrozenASTEncoder", FakeEncoder)
        self.encoder_patch.start()
        self.addCleanup(self.encoder_patch.stop)
        self.stdout_patch = redirect_stdout(io.StringIO())
        self.stdout_patch.__enter__()
        self.addCleanup(self.stdout_patch.__exit__, None, None, None)

    def audio(self, name: str, value: bytes) -> Path:
        path = self.root / name
        path.write_bytes(value)
        return path

    def extract(self, examples: list[PatientExample]) -> np.ndarray:
        return ast.extract_patient_embeddings(examples, self.output, self.config)

    def test_patient_aggregation_gives_each_clip_equal_weight(self) -> None:
        first = patient(self.audio("short.wav", b"2"), self.audio("long.wav", b"00008"))
        second = patient(self.audio("other.wav", b"20"))
        result = self.extract([first, second])
        self.assertEqual(result.shape, (2, ast.EMBEDDING_DIM))
        self.assertEqual(result.dtype, np.float32)
        np.testing.assert_array_equal(result[:, 0], [5, 20])
        self.assertEqual(FakeEncoder.instances[0].calls, [[b"2", b"00008"], [b"20"]])
        self.assertEqual(FakeEncoder.instances[0].model_dir, ast.local_model_dir(self.output, self.config))

    def test_mixed_hits_and_misses_keep_exact_input_order(self) -> None:
        first = patient(self.audio("first.wav", b"1"))
        second = patient(self.audio("second.wav", b"2"))
        third = patient(self.audio("third.wav", b"3"))
        self.extract([first, third])
        result = self.extract([third, second, first, second])
        np.testing.assert_array_equal(result[:, 0], [3, 2, 1, 2])
        self.assertEqual(FakeEncoder.instances[-1].calls, [[b"2"]])

    def test_all_cache_hits_do_not_construct_or_download_encoder(self) -> None:
        example = patient(self.audio("clip.wav", b"4"))
        expected = self.extract([example])
        with patch.object(ast, "FrozenASTEncoder", side_effect=AssertionError("unexpected model load")):
            actual = self.extract([example])
        np.testing.assert_array_equal(actual, expected)

    def test_content_change_invalidates_cache_but_rename_does_not(self) -> None:
        path = self.audio("clip.wav", b"4")
        self.extract([patient(path)])
        renamed = self.root / "renamed.wav"
        path.rename(renamed)
        self.extract([patient(renamed, patient_id="different-id")])
        self.assertEqual(len(FakeEncoder.instances), 1)
        renamed.write_bytes(b"9")
        result = self.extract([patient(renamed)])
        np.testing.assert_array_equal(result[:, 0], [9])
        self.assertEqual(len(FakeEncoder.instances), 2)
        self.assertEqual(len(list((self.output / "ast_cache").glob("*.npz"))), 2)

    def test_cache_hash_includes_revision_preprocessing_and_clip_multiplicity(self) -> None:
        key = ast._patient_cache_key([b"1"], self.config)
        different_revision = types.SimpleNamespace(model_id=ast.MODEL_ID, revision="other")
        self.assertNotEqual(key, ast._patient_cache_key([b"1"], different_revision))
        self.assertNotEqual(key, ast._patient_cache_key([b"1", b"1"], self.config))
        with patch.object(ast, "PREPROCESSING_ID", "new-recipe"):
            self.assertNotEqual(key, ast._patient_cache_key([b"1"], self.config))

    def test_each_patient_cache_is_safe_numeric_npz_and_has_no_partial_files(self) -> None:
        self.extract([patient(self.audio("clip.wav", b"2"))])
        directory = self.output / "ast_cache"
        files = list(directory.iterdir())
        self.assertEqual(len(files), 1)
        with np.load(files[0], allow_pickle=False) as cache:
            self.assertEqual(cache["cache_key"].item(), files[0].stem)
            self.assertEqual(cache["embedding"].shape, (ast.EMBEDDING_DIM,))
            self.assertEqual(cache["embedding"].dtype, np.float32)

    def test_corrupt_nonfinite_or_pickle_cache_is_rejected(self) -> None:
        example = patient(self.audio("clip.wav", b"2"))
        self.extract([example])
        path = next((self.output / "ast_cache").glob("*.npz"))
        for embedding in (np.full(ast.EMBEDDING_DIM, np.nan), np.array([object()], dtype=object)):
            np.savez(path, embedding=embedding, cache_key=np.asarray(path.stem))
            with self.assertRaisesRegex(ValueError, "Invalid AST cache"):
                self.extract([example])
        path.write_bytes(b"broken archive")
        with self.assertRaisesRegex(ValueError, "Invalid AST cache"):
            self.extract([example])

    def test_empty_missing_audio_and_nonfinite_features_are_rejected(self) -> None:
        for examples in ([], [patient()], [patient(self.root / "absent.wav")],
                         [patient(self.audio("empty.wav", b""))]):
            with self.assertRaises(ValueError):
                self.extract(examples)
        example = patient(self.audio("clip.wav", b"2"))
        with patch.object(FakeEncoder, "embed_bytes", return_value=np.full((1, ast.EMBEDDING_DIM), np.inf)):
            with self.assertRaisesRegex(ValueError, "nonfinite"):
                self.extract([example])
        self.assertFalse(list((self.output / "ast_cache").glob("*.npz")))

    def test_atomic_write_failure_leaves_no_partial_file(self) -> None:
        destination = self.root / "embedding.npz"
        with patch.object(ast.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                ast._atomic_write(destination, lambda stream: stream.write(b"partial"))
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.root.glob("*.tmp")))


class EncoderContractTests(unittest.TestCase):
    def test_config_is_pinned_and_cuda_is_default(self) -> None:
        config = ast.ASTConfig()
        self.assertEqual(config.model_id, "MIT/ast-finetuned-audioset-10-10-0.4593")
        self.assertEqual(config.revision, "f826b80d28226b62986cc218e5cec390b1096902")
        self.assertEqual(config.device, "cuda")
        self.assertEqual(config.batch_size, 4)
        for kwargs in ({"model_id": "untrusted/model"}, {"revision": "main"},
                       {"batch_size": 0}, {"batch_size": True}, {"batch_size": 1.5},
                       {"device": "auto"}):
            with self.assertRaises(ValueError):
                ast.ASTConfig(**kwargs)

    def test_cuda_unavailable_fails_before_snapshot_download(self) -> None:
        torch = types.ModuleType("torch")
        torch.device = lambda name: types.SimpleNamespace(type="cuda", index=None)
        torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        with patch.dict("sys.modules", {"torch": torch}):
            with patch.object(ast, "_ensure_snapshot", side_effect=AssertionError("download attempted")):
                with self.assertRaisesRegex(RuntimeError, "requires CUDA.*no CPU fallback"):
                    ast.FrozenASTEncoder(ast.ASTConfig(), Path("unused"))

    def test_embed_paths_batches_in_order_and_decodes_once(self) -> None:
        encoder = object.__new__(ast.FrozenASTEncoder)
        encoder.config = ast.ASTConfig(batch_size=2)
        paths = [Path(f"{index}.wav") for index in range(5)]
        batch_sizes = []

        def embed(waveforms: list[np.ndarray]) -> np.ndarray:
            batch_sizes.append(len(waveforms))
            return np.stack([np.full(ast.EMBEDDING_DIM, waveform[0]) for waveform in waveforms])

        with patch.object(ast, "_read_audio", side_effect=[b"0", b"1", b"2", b"3", b"4"]):
            with patch.object(encoder, "prepare_waveform", side_effect=lambda audio: np.array([int(audio)])) as decode:
                with patch.object(encoder, "_embed_waveforms", side_effect=embed):
                    with patch.object(encoder, "_report_batch") as progress:
                        embeddings = encoder.embed_paths(paths)
                        from_bytes = encoder.embed_bytes([b"0", b"1", b"2", b"3", b"4"])
        np.testing.assert_array_equal(embeddings[:, 0], np.arange(5))
        np.testing.assert_array_equal(from_bytes, embeddings)
        self.assertEqual(decode.call_count, 10)
        self.assertEqual(batch_sizes, [2, 2, 1, 2, 2, 1])
        self.assertEqual(progress.call_count, 6)
        with self.assertRaisesRegex(ValueError, "at least one"):
            encoder.embed_paths([])

    def test_local_load_is_safe_frozen_and_uses_only_pooler_output(self) -> None:
        expected = np.full((2, ast.EMBEDDING_DIM), 7, dtype=np.float32)

        class Tensor:
            def to(self, device: object) -> Tensor:
                return self

            def detach(self) -> Tensor:
                return self

            def cpu(self) -> Tensor:
                return self

            def numpy(self) -> np.ndarray:
                return expected

        torch = types.ModuleType("torch")
        torch.device = lambda name: types.SimpleNamespace(type="cpu", index=None)
        torch.inference_mode = Mock(side_effect=nullcontext)
        extractor = Mock(return_value={"input_values": Tensor()})
        model = Mock(return_value=types.SimpleNamespace(
            pooler_output=Tensor(), last_hidden_state=None,
        ))
        transformers = types.ModuleType("transformers")
        transformers.ASTFeatureExtractor = types.SimpleNamespace(from_pretrained=Mock(return_value=extractor))
        transformers.ASTModel = types.SimpleNamespace(from_pretrained=Mock(return_value=model))
        with patch.dict("sys.modules", {"torch": torch, "transformers": transformers}):
            with patch.object(ast, "_ensure_snapshot"):
                encoder = ast.FrozenASTEncoder(ast.ASTConfig(device="cpu"), Path("local-snapshot"))
                waveforms = [np.zeros(400, dtype=np.float32), np.zeros(800, dtype=np.float32)]
                actual = encoder._embed_waveforms(waveforms)
                with self.assertRaisesRegex(ValueError, "25 ms"):
                    encoder._embed_waveforms([np.zeros(399, dtype=np.float32)])
                model.return_value = types.SimpleNamespace(pooler_output=None)
                with self.assertRaisesRegex(ValueError, "pooler_output"):
                    encoder._embed_waveforms(waveforms)
        transformers.ASTFeatureExtractor.from_pretrained.assert_called_once_with(
            "local-snapshot", local_files_only=True, trust_remote_code=False,
        )
        transformers.ASTModel.from_pretrained.assert_called_once_with(
            "local-snapshot", local_files_only=True, use_safetensors=True, trust_remote_code=False,
        )
        model.eval.assert_called_once_with()
        model.requires_grad_.assert_called_once_with(False)
        self.assertEqual(torch.inference_mode.call_count, 2)
        self.assertEqual(extractor.call_count, 2)
        extractor.assert_called_with(waveforms, sampling_rate=16000, return_tensors="pt")
        np.testing.assert_array_equal(actual, expected)

    def test_progress_reports_elapsed_gpu_and_flushes(self) -> None:
        encoder = object.__new__(ast.FrozenASTEncoder)
        encoder.device = types.SimpleNamespace(type="cpu")
        with patch.object(ast.time, "monotonic", return_value=12.0):
            with patch("builtins.print") as report:
                encoder._report_batch(4, 8, 10.0)
        message = report.call_args.args[0]
        self.assertIn("clips=4/8 elapsed=2.0s", message)
        self.assertIn("GPU=disabled (explicit CPU)", message)
        self.assertTrue(report.call_args.kwargs["flush"])

    def test_local_snapshot_is_restricted_pinned_and_reusable_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            model_dir = Path(temporary)
            hub = types.ModuleType("huggingface_hub")
            calls = []

            def download(**kwargs: object) -> str:
                calls.append(kwargs)
                for filename in ast.SNAPSHOT_FILES:
                    (model_dir / filename).write_bytes(filename.encode())
                return str(model_dir)

            hub.snapshot_download = download
            with patch.dict("sys.modules", {"huggingface_hub": hub}):
                ast._ensure_snapshot(model_dir, ast.ASTConfig())
                ast._ensure_snapshot(model_dir, ast.ASTConfig())
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["repo_id"], ast.MODEL_ID)
            self.assertEqual(calls[0]["revision"], ast.REVISION)
            self.assertEqual(calls[0]["allow_patterns"], list(ast.SNAPSHOT_FILES))
            manifest = json.loads((model_dir / "ast_provenance.json").read_text())
            self.assertEqual(manifest["sha256"]["model.safetensors"],
                             hashlib.sha256(b"model.safetensors").hexdigest())
            (model_dir / "model.safetensors").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "Invalid AST local snapshot"):
                ast._ensure_snapshot(model_dir, ast.ASTConfig())


if __name__ == "__main__":
    unittest.main()
