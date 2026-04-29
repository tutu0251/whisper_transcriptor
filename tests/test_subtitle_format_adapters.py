"""
Tests for subtitle format adapters.
"""

import tempfile
import unittest
from pathlib import Path

from src.core.subtitle_format_adapters import (
    ASSAdapter,
    LRCAdapter,
    SBVAdapter,
    SMIAdapter,
    SRTAdapter,
    SSAAdapter,
    SUBAdapter,
    SubtitleFormatRegistry,
    VTTAdapter,
)


class TestSubtitleFormatAdapters(unittest.TestCase):
    def test_srt_adapter_round_trips_into_document(self):
        content = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n"
        document = SRTAdapter().parse(content)

        self.assertEqual(document.format, "srt")
        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "Hello world")

        exported = SRTAdapter().serialize(document)
        self.assertIn("00:00:01,000 --> 00:00:03,000", exported)
        self.assertIn("Hello world", exported)

    def test_smi_adapter_parses_sync_blocks(self):
        content = (
            "<SAMI><BODY>\n"
            "<SYNC Start=1000><P Class=ENCC>Hello<br>there\n"
            "<SYNC Start=3000><P Class=ENCC>Next line\n"
            "</BODY></SAMI>"
        )
        document = SMIAdapter().parse(content)

        self.assertEqual(document.format, "smi")
        self.assertEqual(len(document.segments), 2)
        self.assertEqual(document.segments[0].text, "Hello\nthere")
        self.assertAlmostEqual(document.segments[0].start_time, 1.0)
        self.assertAlmostEqual(document.segments[0].end_time, 3.0)

        exported = SMIAdapter().serialize(document)
        self.assertIn("<SYNC Start=1000>", exported)
        self.assertIn("Hello<BR>there", exported)

    def test_vtt_adapter_parses_and_serializes_cues(self):
        content = "WEBVTT\n\ncue-1\n00:00:01.000 --> 00:00:03.500\nHello <b>world</b>\n"
        document = VTTAdapter().parse(content)

        self.assertEqual(document.format, "vtt")
        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "Hello world")
        self.assertAlmostEqual(document.segments[0].end_time, 3.5)

        exported = VTTAdapter().serialize(document)
        self.assertIn("WEBVTT", exported)
        self.assertIn("00:00:01.000 --> 00:00:03.500", exported)

    def test_ass_adapter_parses_dialogue_events(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:03.25,Default,,0,0,0,,Hello{\\i1}\\Nthere\n"
        )
        document = ASSAdapter().parse(content)

        self.assertEqual(document.format, "ass")
        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "Hello\nthere")
        self.assertAlmostEqual(document.segments[0].end_time, 3.25)

        exported = ASSAdapter().serialize(document)
        self.assertIn("[Events]", exported)
        self.assertIn("Dialogue: 0,0:00:01.00,0:00:03.25", exported)

    def test_ssa_adapter_uses_same_dialogue_path(self):
        content = (
            "[Events]\n"
            "Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: Marked=0,0:00:02.00,0:00:04.00,Default,,0,0,0,,SSA text\n"
        )
        document = SSAAdapter().parse(content)

        self.assertEqual(document.format, "ssa")
        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "SSA text")

    def test_sub_adapter_parses_subviewer_blocks(self):
        content = "00:00:01.00,00:00:03.00\nHello\nthere\n\n"
        document = SUBAdapter().parse(content)

        self.assertEqual(document.format, "sub")
        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "Hello\nthere")

        exported = SUBAdapter().serialize(document)
        self.assertIn("00:00:01.00,00:00:03.00", exported)

    def test_sub_adapter_parses_microdvd_blocks(self):
        document = SUBAdapter().parse("{25}{75}Hello|there\n")

        self.assertEqual(len(document.segments), 1)
        self.assertEqual(document.segments[0].text, "Hello\nthere")
        self.assertAlmostEqual(document.segments[0].start_time, 1.0)
        self.assertAlmostEqual(document.segments[0].end_time, 3.0)

    def test_sbv_adapter_parses_youtube_blocks(self):
        content = "0:00:01.000,0:00:03.000\nHello\nthere\n\n0:00:04.000,0:00:05.000\nNext\n"
        document = SBVAdapter().parse(content)

        self.assertEqual(document.format, "sbv")
        self.assertEqual(len(document.segments), 2)
        self.assertEqual(document.segments[0].text, "Hello\nthere")
        self.assertAlmostEqual(document.segments[1].start_time, 4.0)

        exported = SBVAdapter().serialize(document)
        self.assertIn("00:00:01.000,00:00:03.000", exported)

    def test_lrc_adapter_uses_next_timestamp_as_end_time(self):
        content = "[00:01.00]First line\n[00:03.50]Second line\n"
        document = LRCAdapter().parse(content)

        self.assertEqual(document.format, "lrc")
        self.assertEqual(len(document.segments), 2)
        self.assertAlmostEqual(document.segments[0].start_time, 1.0)
        self.assertAlmostEqual(document.segments[0].end_time, 3.5)

        exported = LRCAdapter().serialize(document)
        self.assertIn("[00:01.00]First line", exported)

    def test_registry_exposes_all_planned_formats(self):
        self.assertEqual(
            set(SubtitleFormatRegistry.supported_formats()),
            {"SRT", "SMI", "VTT", "ASS", "SSA", "SUB", "SBV", "LRC"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "sample.vtt"
            subtitle_path.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nText\n", encoding="utf-8")
            document = SubtitleFormatRegistry.get_adapter_for_path(str(subtitle_path)).import_file(str(subtitle_path))

        self.assertEqual(document.format, "vtt")
        self.assertEqual(document.segments[0].text, "Text")
