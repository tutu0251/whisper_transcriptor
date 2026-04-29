"""
Tests for subtitle format adapters.
"""

import unittest

from src.core.subtitle_format_adapters import SMIAdapter, SRTAdapter


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
