"""
Tests for transcription panel correction storage.
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "src" / "gui" / "transcription_panel.py"

spec = importlib.util.spec_from_file_location("transcription_panel_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TranscriptionPanel = module.TranscriptionPanel


class FakeDatabase:
    def __init__(self):
        self.corrections = []

    def add_correction(self, correction_data):
        self.corrections.append(correction_data)
        return len(self.corrections)

    def get_statistics(self):
        return {"pending_corrections": len(self.corrections)}


class RejectingCollector:
    def __init__(self, database):
        self.database = database

    def collect_correction(self, *args, **kwargs):
        return False

    def get_pending_count(self):
        return self.database.get_statistics()["pending_corrections"]


class TestTranscriptionPanelCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_store_correction_increases_pending_count(self):
        panel = TranscriptionPanel()
        database = FakeDatabase()
        panel.set_database_manager(database)

        emitted = []
        panel.correction_made.connect(emitted.append)

        panel._store_correction(
            "original text",
            "corrected text",
            confidence=0.6,
            start_time=1.0,
            end_time=2.0,
            file_path="sample.wav",
            language="es",
        )

        self.assertEqual(len(database.corrections), 1)
        self.assertEqual(database.corrections[0]["language"], "es")
        self.assertEqual(emitted[-1]["pending_count"], 1)
        self.assertTrue(emitted[-1]["stored"])
        self.assertEqual(emitted[-1]["original_text"], "original text")
        self.assertEqual(emitted[-1]["corrected_text"], "corrected text")
        self.assertEqual(emitted[-1]["language"], "es")

    def test_store_correction_falls_back_when_collector_rejects(self):
        panel = TranscriptionPanel()
        database = FakeDatabase()
        panel.set_database_manager(database)
        panel.set_correction_collector(RejectingCollector(database))

        emitted = []
        panel.correction_made.connect(emitted.append)

        panel._store_correction(
            "original text",
            "corrected text",
            confidence=0.6,
            start_time=1.0,
            end_time=2.0,
            file_path="sample.wav",
            language="fr",
        )

        self.assertEqual(len(database.corrections), 1)
        self.assertEqual(database.corrections[0]["language"], "fr")
        self.assertEqual(emitted[-1]["pending_count"], 1)
        self.assertEqual(emitted[-1]["language"], "fr")


if __name__ == "__main__":
    unittest.main()
