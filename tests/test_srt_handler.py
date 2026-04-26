"""
Tests for SRT Handler Module
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "src" / "core" / "srt_handler.py"

spec = importlib.util.spec_from_file_location("srt_handler_module", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SRTEntry = module.SRTEntry
SRTHandler = module.SRTHandler


class TestSRTHandler(unittest.TestCase):
    """Test cases for SRTHandler class"""

    def setUp(self):
        """Set up test fixtures"""
        self.handler = SRTHandler()
        self.temp_dir = tempfile.mkdtemp()

    def test_seconds_to_srt_time(self):
        srt_time = self.handler.seconds_to_srt_time(3661.456)
        self.assertEqual(srt_time, "01:01:01,456")

    def test_srt_time_to_seconds(self):
        seconds = self.handler.srt_time_to_seconds("01:01:01,456")
        self.assertAlmostEqual(seconds, 3661.456, places=3)

    def test_parse_srt(self):
        sample = (
            "1\n"
            "00:00:01,000 --> 00:00:03,500\n"
            "Hello world.\n\n"
            "2\n"
            "00:00:04,000 --> 00:00:06,000\n"
            "This is a second line."
        )

        entries = self.handler.parse_srt(sample)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].index, 1)
        self.assertEqual(entries[0].text, "Hello world.")
        self.assertAlmostEqual(entries[0].start_time, 1.0)
        self.assertAlmostEqual(entries[0].end_time, 3.5)
        self.assertEqual(entries[1].index, 2)
        self.assertEqual(entries[1].text, "This is a second line.")

    def test_generate_srt(self):
        entries = [
            SRTEntry(index=1, start_time=0.0, end_time=1.234, text="Test line."),
            SRTEntry(index=2, start_time=1.5, end_time=2.5, text="Another line.")
        ]

        content = self.handler.generate_srt(entries)

        self.assertIn("1", content)
        self.assertIn("00:00:00,000 --> 00:00:01,234", content)
        self.assertIn("Test line.", content)
        self.assertIn("2", content)
        self.assertIn("00:00:01,500 --> 00:00:02,500", content)

    def test_save_and_load_file(self):
        entries = [
            SRTEntry(index=1, start_time=0.0, end_time=1.0, text="Saved line."),
            SRTEntry(index=2, start_time=1.0, end_time=2.0, text="Second saved line.")
        ]

        output_path = Path(self.temp_dir) / "test_output.srt"
        saved = self.handler.save_file(str(output_path), entries)

        self.assertTrue(saved)
        loaded = self.handler.load_file(str(output_path))
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].text, "Saved line.")
        self.assertEqual(loaded[1].text, "Second saved line.")

    def tearDown(self):
        """Clean up after tests"""
        import shutil
        shutil.rmtree(self.temp_dir)


if __name__ == "__main__":
    unittest.main()
