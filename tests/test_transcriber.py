"""
Tests for Transcriber Module
"""

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "src" / "core" / "transcriber.py"

spec = importlib.util.spec_from_file_location("transcriber_module", MODULE_PATH)
transcriber_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transcriber_module)
Transcriber = transcriber_module.Transcriber


class ImmediateThread:
    def __init__(self, target=None, args=None, kwargs=None):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}

    def start(self):
        if self.target:
            self.target(*self.args, **self.kwargs)


class TestTranscriber(unittest.TestCase):
    """Test cases for Transcriber class"""

    def setUp(self):
        self.find_model_patcher = patch.object(
            Transcriber,
            "_find_local_hf_model",
            return_value=None
        )
        self.find_model_patcher.start()

    def tearDown(self):
        self.find_model_patcher.stop()

    @patch.object(transcriber_module, 'torch', new_callable=Mock)
    def test_resolve_device_auto_cpu(self, mock_torch):
        mock_torch.cuda.is_available.return_value = False
        transcriber = Transcriber(device="auto")
        self.assertEqual(transcriber.device, "cpu")

    @patch.object(transcriber_module, 'torch', new_callable=Mock)
    def test_resolve_device_auto_cuda(self, mock_torch):
        mock_torch.cuda.is_available.return_value = True
        transcriber = Transcriber(device="auto")
        self.assertEqual(transcriber.device, "cuda")

    @patch.object(transcriber_module, 'TRANSFORMERS_AVAILABLE', True)
    def test_set_language_updates_model_generation_config(self):
        transcriber = Transcriber(device="cpu")
        generation_config = Mock()
        transcriber.model = Mock(generation_config=generation_config)

        transcriber.set_language("fr")

        self.assertEqual(transcriber.language, "fr")
        self.assertEqual(transcriber.model.generation_config.language, "fr")

    @patch.object(transcriber_module, 'FASTER_WHISPER_AVAILABLE', True)
    def test_transcribe_chunk_with_faster_whisper(self):
        transcriber = Transcriber(device="cpu")
        transcriber.is_loaded = True

        fake_segment = Mock(text="hello world")
        fake_model = Mock()
        fake_model.transcribe.return_value = ([fake_segment], None)
        transcriber.model = fake_model

        text = transcriber.transcribe_chunk("audio_chunk")

        self.assertEqual(text, "hello world")
        fake_model.transcribe.assert_called_once()

    def test_transcribe_chunk_with_openai_whisper_dict_result(self):
        transcriber = Transcriber(device="cpu")
        transcriber.is_loaded = True

        fake_model = Mock()
        fake_model.transcribe.return_value = {"text": " hello world "}
        transcriber.model = fake_model

        text = transcriber.transcribe_chunk("audio_chunk")

        self.assertEqual(text, "hello world")
        fake_model.transcribe.assert_called_once()

    @patch.object(transcriber_module, 'FASTER_WHISPER_AVAILABLE', True)
    def test_transcribe_with_sentences_marks_sentence_boundaries(self):
        transcriber = Transcriber(device="cpu")
        transcriber.is_loaded = True

        segment_one = Mock(text="Hello world.", start=0.0, end=1.2, avg_logprob=0.95)
        segment_two = Mock(text="This is a test", start=1.2, end=2.3, avg_logprob=0.80)
        fake_model = Mock()
        fake_model.transcribe.return_value = ([segment_one, segment_two], None)
        transcriber.model = fake_model

        result = transcriber.transcribe_with_sentences("audio_chunk")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "Hello world.")
        self.assertTrue(result[0]["is_sentence_end"])
        self.assertEqual(result[1]["text"], "This is a test")
        self.assertFalse(result[1]["is_sentence_end"])

    def test_transcribe_file_invokes_callback_for_each_chunk(self):
        transcriber = Transcriber(device="cpu")
        transcriber.transcribe_chunk = Mock(return_value="hello")

        audio = [0.0] * (16000 * 2)
        fake_librosa = types.SimpleNamespace(load=Mock(return_value=(audio, 16000)))

        callback_results = []

        def callback(text, start, end):
            callback_results.append((text, start, end))

        sys.modules["librosa"] = fake_librosa

        with patch.object(transcriber_module.threading, "Thread", new=ImmediateThread):
            transcriber.transcribe_file("dummy.wav", callback)

        self.assertTrue(callback_results)
        self.assertEqual(callback_results[0][0], "hello")
        self.assertEqual(callback_results[0][1], 0.0)
        self.assertEqual(callback_results[0][2], 2.0)

        del sys.modules["librosa"]


if __name__ == "__main__":
    unittest.main()
