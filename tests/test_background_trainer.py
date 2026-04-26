"""
Tests for background training model naming.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "src" / "learning" / "background_trainer.py"

spec = importlib.util.spec_from_file_location("background_trainer_module", MODULE_PATH)
background_trainer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(background_trainer_module)
BackgroundTrainer = background_trainer_module.BackgroundTrainer


class FakeDatabase:
    def __init__(self):
        self.updated_model = None
        self.trained_session = None

    def create_training_session(self):
        return 1

    def update_training_session(self, session_id, new_model, corrections_count, wer_before, wer_after):
        self.updated_model = Path(new_model)

    def mark_corrections_trained(self, correction_ids, session_id):
        self.trained_session = session_id

    def fail_training_session(self, session_id, error=None):
        raise AssertionError(f"Training unexpectedly failed: {error}")


class TestBackgroundTrainerNaming(unittest.TestCase):
    """Test cases for trained model version naming."""

    def make_trainer(self, models_dir, base_model="models/whisper-tiny"):
        trainer = BackgroundTrainer.__new__(BackgroundTrainer)
        trainer.db = FakeDatabase()
        trainer.transcriber = SimpleNamespace(
            custom_model_path=base_model,
            model_size="tiny",
            model=None
        )
        trainer.models_dir = Path(models_dir)
        trainer.learning_rate = 1e-5
        trainer.num_epochs = 3
        trainer.training_callback = None
        trainer.training_in_progress = False
        return trainer

    def test_base_model_name_uses_original_whisper_model_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            trainer = self.make_trainer(temp_dir)

            self.assertEqual(
                trainer._base_model_name("models/whisper-tiny"),
                "whisper_tiny"
            )
            self.assertEqual(
                trainer._base_model_name("whisper-large-v2"),
                "whisper_large_v2"
            )

    def test_next_trained_model_name_increments_per_base_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            (models_dir / "whisper_tiny_v1").mkdir()
            (models_dir / "whisper_base_v1").mkdir()
            trainer = self.make_trainer(models_dir)

            self.assertEqual(
                trainer._next_trained_model_name("models/whisper-tiny"),
                "whisper_tiny_v2"
            )

    @patch.object(background_trainer_module, "TRANSFORMERS_AVAILABLE", False)
    def test_train_simple_saves_model_dir_named_after_base_model(self):
        corrections = [{
            "id": 7,
            "original_text": "helo",
            "corrected_text": "hello",
            "confidence": 0.5,
        }]

        with tempfile.TemporaryDirectory() as temp_dir:
            trainer = self.make_trainer(temp_dir, base_model="models/whisper-tiny")

            trainer._train_simple(corrections)

            model_dir = Path(temp_dir) / "whisper_tiny_v1"
            info = json.loads((model_dir / "model_info.json").read_text(encoding="utf-8"))
            self.assertTrue(model_dir.exists())

        self.assertEqual(info["model_name"], "whisper_tiny_v1")
        self.assertEqual(info["base_model"], "models/whisper-tiny")
        self.assertEqual(trainer.db.updated_model.name, "whisper_tiny_v1")
        self.assertEqual(trainer.db.trained_session, 1)


if __name__ == "__main__":
    unittest.main()
