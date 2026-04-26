"""
Unit tests for model selection functionality
Tests model manager operations and transcriber configuration
"""

import os
import unittest
import tempfile
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.model_manager import ModelManager
from src.core.transcriber import Transcriber

MAIN_WINDOW_PATH = Path(__file__).resolve().parent.parent / "src" / "gui" / "main_window.py"
main_window_spec = importlib.util.spec_from_file_location("main_window_module", MAIN_WINDOW_PATH)
main_window_module = importlib.util.module_from_spec(main_window_spec)
main_window_spec.loader.exec_module(main_window_module)
MainWindow = main_window_module.MainWindow


class TestModelManager(unittest.TestCase):
    """Test ModelManager functionality"""

    def setUp(self):
        self.model_manager = ModelManager(cache_dir="/tmp/test_whisper_cache")

    def test_get_hf_model_id_tiny(self):
        """Test getting HF model ID for tiny"""
        result = self.model_manager.get_hf_model_id("tiny")
        self.assertEqual(result, "openai/whisper-tiny")

    def test_get_hf_model_id_base(self):
        """Test getting HF model ID for base"""
        result = self.model_manager.get_hf_model_id("base")
        self.assertEqual(result, "openai/whisper-base")

    def test_get_hf_model_id_large(self):
        """Test getting HF model ID for large (v2)"""
        result = self.model_manager.get_hf_model_id("large")
        self.assertEqual(result, "openai/whisper-large-v2")

    def test_get_hf_model_path(self):
        """Test getting HF model path"""
        path = self.model_manager.get_hf_model_path("openai/whisper-tiny")
        self.assertIn("whisper-tiny", str(path))

    def test_get_custom_model_path(self):
        """Test getting custom model path"""
        path = self.model_manager.get_custom_model_path("my_model")
        self.assertIn("custom", str(path))
        self.assertIn("my_model", str(path))

    def test_is_hf_model_available_with_safetensors(self):
        """Test HF availability check with safetensors weights."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(cache_dir=temp_dir)
            model_dir = manager.get_hf_model_path("openai/whisper-tiny")
            model_dir.mkdir(parents=True, exist_ok=True)

            for name in (
                "config.json",
                "tokenizer_config.json",
                "preprocessor_config.json",
                "tokenizer.json",
                "model.safetensors",
            ):
                (model_dir / name).write_text("{}", encoding="utf-8")

            self.assertTrue(manager.is_hf_model_available("openai/whisper-tiny"))

    def test_is_hf_model_available_with_pytorch_bin(self):
        """Test HF availability check with pytorch_model.bin weights."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(cache_dir=temp_dir)
            model_dir = manager.get_hf_model_path("openai/whisper-tiny")
            model_dir.mkdir(parents=True, exist_ok=True)

            for name in (
                "config.json",
                "tokenizer_config.json",
                "preprocessor_config.json",
                "tokenizer.json",
                "pytorch_model.bin",
            ):
                (model_dir / name).write_text("{}", encoding="utf-8")

            self.assertTrue(manager.is_hf_model_available("openai/whisper-tiny"))

    @patch("huggingface_hub.snapshot_download")
    def test_download_hf_model_uses_essential_patterns(self, mock_snapshot_download):
        """Test that HF downloads default to essential files only."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ModelManager(cache_dir=temp_dir)
            model_dir = manager.get_hf_model_path("openai/whisper-tiny")

            def fake_download(**kwargs):
                model_dir.mkdir(parents=True, exist_ok=True)
                for name in (
                    "config.json",
                    "tokenizer_config.json",
                    "preprocessor_config.json",
                    "tokenizer.json",
                    "model.safetensors",
                ):
                    (model_dir / name).write_text("{}", encoding="utf-8")

            mock_snapshot_download.side_effect = fake_download

            self.assertTrue(manager.download_hf_model("tiny"))
            _, kwargs = mock_snapshot_download.call_args
            self.assertEqual(
                kwargs["allow_patterns"],
                ModelManager.HF_ESSENTIAL_ALLOW_PATTERNS,
            )

    def test_list_models_not_empty(self):
        """Test that list_models returns models"""
        models = self.model_manager.list_models()
        self.assertGreater(len(models), 0)

    def test_list_models_has_tiny(self):
        """Test that list includes tiny model"""
        models = self.model_manager.list_models()
        names = [m.name for m in models]
        self.assertIn("tiny", names)

    def test_list_models_has_large(self):
        """Test that list includes large model"""
        models = self.model_manager.list_models()
        names = [m.name for m in models]
        self.assertIn("large", names)


class TestTranscriberConfiguration(unittest.TestCase):
    """Test Transcriber model configuration"""

    def test_transcriber_model_size(self):
        """Test transcriber model size parameter"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            self.assertEqual(transcriber.model_size, "tiny")

    def test_transcriber_device(self):
        """Test transcriber device parameter"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            self.assertEqual(transcriber.device, "cpu")

    def test_transcriber_compute_type(self):
        """Test transcriber compute type"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(
                model_size="tiny",
                device="cpu",
                compute_type="float32"
            )
            self.assertEqual(transcriber.compute_type, "float32")

    def test_transcriber_language(self):
        """Test transcriber language parameter"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(
                model_size="tiny",
                device="cpu",
                language="en"
            )
            self.assertEqual(transcriber.language, "en")

    def test_transcriber_custom_path(self):
        """Test transcriber with custom model path"""
        transcriber = Transcriber(
            model_size="custom",
            device="cpu",
            custom_model_path="/path/to/model"
        )
        self.assertEqual(transcriber.custom_model_path, "/path/to/model")
        self.assertEqual(transcriber.model_type, "custom")

    def test_transcriber_is_not_loaded_initially(self):
        """Test that model is not loaded initially"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            self.assertFalse(transcriber.is_loaded)


class TestModelSelection(unittest.TestCase):
    """Test model selection scenarios"""

    def test_select_tiny_model(self):
        """Test selecting tiny model"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            self.assertEqual(transcriber.model_size, "tiny")

    def test_select_base_model(self):
        """Test selecting base model"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="base", device="cpu")
            self.assertEqual(transcriber.model_size, "base")

    def test_select_small_model(self):
        """Test selecting small model"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="small", device="cpu")
            self.assertEqual(transcriber.model_size, "small")

    def test_select_medium_model(self):
        """Test selecting medium model"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="medium", device="cpu")
            self.assertEqual(transcriber.model_size, "medium")

    def test_select_large_model(self):
        """Test selecting large model"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="large", device="cpu")
            self.assertEqual(transcriber.model_size, "large")

    def test_select_base_model_prefers_matching_local_hf_folder(self):
        """Test that local HF auto-detection respects the requested model size."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                models_dir = Path(temp_dir) / "models"
                tiny_dir = models_dir / "whisper-tiny"
                base_dir = models_dir / "whisper-base"
                tiny_dir.mkdir(parents=True, exist_ok=True)
                base_dir.mkdir(parents=True, exist_ok=True)
                (tiny_dir / "config.json").write_text("{}", encoding="utf-8")
                (base_dir / "config.json").write_text("{}", encoding="utf-8")

                transcriber = Transcriber(model_size="base", device="cpu")

                self.assertEqual(transcriber.model_type, "custom")
                self.assertEqual(Path(transcriber.custom_model_path).name, "whisper-base")
            finally:
                os.chdir(cwd)


class TestModelTypes(unittest.TestCase):
    """Test different model types"""

    def test_standard_model_type(self):
        """Test standard model identification"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            self.assertEqual(transcriber.model_type, "standard")

    def test_custom_model_type(self):
        """Test custom model identification"""
        transcriber = Transcriber(
            model_size="custom",
            device="cpu",
            custom_model_path="/path"
        )
        self.assertEqual(transcriber.model_type, "custom")


class TestLanguageSettings(unittest.TestCase):
    """Test language settings for transcriber"""

    def test_set_language_english(self):
        """Test setting language to English"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            transcriber.set_language("en")
            self.assertEqual(transcriber.language, "en")

    def test_set_language_spanish(self):
        """Test setting language to Spanish"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            transcriber.set_language("es")
            self.assertEqual(transcriber.language, "es")

    def test_set_language_auto(self):
        """Test setting language to auto"""
        with patch.object(Transcriber, '_find_local_hf_model', return_value=None):
            transcriber = Transcriber(model_size="tiny", device="cpu")
            transcriber.set_language("auto")
            self.assertEqual(transcriber.language, "auto")


class DummyConfig:
    def __init__(self):
        self.values = {"custom_model_path": "old_path"}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class DummyStatusBar:
    def __init__(self):
        self.messages = []

    def set_status(self, message):
        self.messages.append(message)


class DummyAction:
    def __init__(self):
        self.checked = None

    def setChecked(self, checked):
        self.checked = checked


class TestMainWindowModelMenu(unittest.TestCase):
    """Test menu-driven model changes on the main window."""

    @patch.object(main_window_module.QApplication, "processEvents")
    def test_change_model_reinitializes_selected_standard_model(self, _mock_process_events):
        window = type("WindowLike", (), {})()
        window.current_model = "tiny"
        window.custom_model_path = "old_path"
        window.config = DummyConfig()
        window.status_bar = DummyStatusBar()
        window.model_manager = MagicMock()
        window.model_manager.get_hf_model_id.return_value = "openai/whisper-base"
        window.model_manager.is_hf_model_available.return_value = True
        window.model_manager.download_hf_model.return_value = True
        window.init_transcriber = MagicMock()
        window.model_actions = {
            "tiny": DummyAction(),
            "base": DummyAction(),
            "small": DummyAction(),
        }

        MainWindow.change_model(window, "base")

        self.assertEqual(window.current_model, "base")
        self.assertIsNone(window.custom_model_path)
        self.assertIsNone(window.config.get("custom_model_path"))
        window.init_transcriber.assert_called_once_with("base")
        self.assertEqual(window.config.get("model_size"), "base")
        self.assertFalse(window.model_actions["tiny"].checked)
        self.assertTrue(window.model_actions["base"].checked)
        self.assertFalse(window.model_actions["small"].checked)

    def test_sync_transcriber_references_updates_background_trainer(self):
        window = type("WindowLike", (), {})()
        window.transcriber = object()
        window.background_trainer = type("TrainerLike", (), {"transcriber": None})()

        MainWindow.sync_transcriber_references(window)

        self.assertIs(window.background_trainer.transcriber, window.transcriber)


if __name__ == '__main__':
    unittest.main()
