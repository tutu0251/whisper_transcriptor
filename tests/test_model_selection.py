"""
Unit tests for model selection functionality
Tests model manager operations and transcriber configuration
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.model_manager import ModelManager
from src.core.transcriber import Transcriber


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


if __name__ == '__main__':
    unittest.main()
