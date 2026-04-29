"""
Subtitle format adapters.

This module normalizes subtitle files into the shared SubtitleDocument model.
"""

from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from src.core.srt_handler import SRTHandler
from src.models.srt_entry import SRTEntry
from src.models.subtitle_document import SubtitleDocument
from src.models.subtitle_segment import SegmentSource, SubtitleSegment


def _add_loaded_segment(document: SubtitleDocument, text: str, start_time: float, end_time: float) -> None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return

    document.segments.append(
        SubtitleSegment(
            index=len(document.segments) + 1,
            text=cleaned_text,
            start_time=max(0.0, start_time),
            end_time=max(start_time + 0.001, end_time),
            confidence=1.0,
            source=SegmentSource.LOADED,
        )
    )


def _parse_clock_timestamp(value: str) -> float:
    match = re.match(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:[,.](\d{1,3}))?\s*$", value)
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value}")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    fraction = match.group(4) or "0"
    milliseconds = int(fraction.ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def _format_clock_timestamp(seconds: float, separator: str = ".") -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _parse_ass_timestamp(value: str) -> float:
    match = re.match(r"^\s*(\d+):(\d{1,2}):(\d{2})(?:[.](\d{1,3}))?\s*$", value)
    if not match:
        raise ValueError(f"Invalid ASS/SSA timestamp: {value}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    fraction = match.group(4) or "0"
    centiseconds = int(fraction.ljust(2, "0")[:2])
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = max(0, int(round(seconds * 100)))
    hours = total_cs // 360_000
    total_cs %= 360_000
    minutes = total_cs // 6_000
    total_cs %= 6_000
    secs = total_cs // 100
    centis = total_cs % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _parse_lrc_timestamp(value: str) -> float:
    match = re.match(r"^(\d+):(\d{2})(?:[.:](\d{1,3}))?$", value.strip())
    if not match:
        raise ValueError(f"Invalid LRC timestamp: {value}")

    minutes = int(match.group(1))
    seconds = int(match.group(2))
    fraction = match.group(3) or "0"
    centiseconds = int(fraction.ljust(2, "0")[:2])
    return minutes * 60 + seconds + centiseconds / 100.0


def _format_lrc_timestamp(seconds: float) -> str:
    total_cs = max(0, int(round(seconds * 100)))
    minutes = total_cs // 6000
    total_cs %= 6000
    secs = total_cs // 100
    centis = total_cs % 100
    return f"{minutes:02d}:{secs:02d}.{centis:02d}"


def _strip_inline_tags(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).replace("\xa0", " ").strip()


class SubtitleFormatAdapter(ABC):
    """Base adapter for importing/exporting subtitle formats."""

    format_name: str = ""
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        """Parse subtitle text into a document."""

    @abstractmethod
    def serialize(self, document: SubtitleDocument) -> str:
        """Serialize a document into subtitle text."""

    def import_file(self, file_path: str) -> SubtitleDocument:
        with open(file_path, "r", encoding="utf-8-sig") as handle:
            return self.parse(handle.read(), source_file=file_path)

    def export_file(self, file_path: str, document: SubtitleDocument) -> None:
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(self.serialize(document))


class SRTAdapter(SubtitleFormatAdapter):
    format_name = "srt"
    extensions = (".srt",)

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        handler = SRTHandler()
        entries = handler.parse_srt(content)
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        for entry in entries:
            document.segments.append(
                SubtitleSegment(
                    index=entry.index,
                    text=entry.text,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    confidence=1.0,
                    source=SegmentSource.LOADED,
                )
            )
        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        handler = SRTHandler()
        entries = document_to_srt_entries(document)
        return handler.generate_srt(entries)


class SMIAdapter(SubtitleFormatAdapter):
    format_name = "smi"
    extensions = (".smi", ".sami")

    sync_pattern = re.compile(
        r"<sync\s+start\s*=\s*(\d+)[^>]*>(.*?)(?=<sync\s+start\s*=|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    tag_pattern = re.compile(r"<[^>]+>")
    break_pattern = re.compile(r"<br\s*/?>", re.IGNORECASE)

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        matches = list(self.sync_pattern.finditer(content))
        for index, match in enumerate(matches, start=1):
            start_ms = int(match.group(1))
            block_text = self._clean_text(match.group(2))
            if not block_text:
                continue

            next_start_ms = None
            if index < len(matches):
                next_start_ms = int(matches[index].group(1))

            end_ms = next_start_ms if next_start_ms is not None else start_ms + 2000
            document.segments.append(
                SubtitleSegment(
                    index=len(document.segments) + 1,
                    text=block_text,
                    start_time=start_ms / 1000.0,
                    end_time=max((start_ms + 1) / 1000.0, end_ms / 1000.0),
                    confidence=1.0,
                    source=SegmentSource.LOADED,
                )
            )

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines = ["<SAMI>", "<BODY>"]
        for segment in document.segments:
            text = html.escape(segment.text).replace("\n", "<BR>")
            lines.append(f'<SYNC Start={int(segment.start_time * 1000)}><P Class=ENCC>{text}')
        lines.extend(["</BODY>", "</SAMI>"])
        return "\n".join(lines)

    def _clean_text(self, text: str) -> str:
        text = self.break_pattern.sub("\n", text)
        text = self.tag_pattern.sub("", text)
        return html.unescape(text).replace("\xa0", " ").strip()


class VTTAdapter(SubtitleFormatAdapter):
    format_name = "vtt"
    extensions = (".vtt",)

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        index = 1 if lines and lines[0].lstrip("\ufeff").strip().upper().startswith("WEBVTT") else 0

        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue

            if line.startswith(("NOTE", "STYLE", "REGION")):
                index += 1
                while index < len(lines) and lines[index].strip():
                    index += 1
                continue

            if "-->" not in line:
                index += 1
                if index >= len(lines):
                    break
                line = lines[index].strip()

            if "-->" not in line:
                index += 1
                continue

            start_text, end_text = line.split("-->", 1)
            end_token = end_text.strip().split()[0]
            start_time = _parse_clock_timestamp(start_text.strip())
            end_time = _parse_clock_timestamp(end_token)

            index += 1
            text_lines: List[str] = []
            while index < len(lines) and lines[index].strip():
                text_lines.append(lines[index])
                index += 1

            _add_loaded_segment(document, _strip_inline_tags("\n".join(text_lines)), start_time, end_time)

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines = ["WEBVTT", ""]
        for segment in document.segments:
            lines.append(str(segment.index or len(lines)))
            lines.append(
                f"{_format_clock_timestamp(segment.start_time)} --> {_format_clock_timestamp(segment.end_time)}"
            )
            lines.extend(html.escape(segment.text).split("\n"))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


class ASSAdapter(SubtitleFormatAdapter):
    format_name = "ass"
    extensions = (".ass",)

    dialogue_prefix = "Dialogue:"

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        in_events = False
        fields: List[str] = []

        for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("[") and line.endswith("]"):
                in_events = line.lower() == "[events]"
                continue

            if not in_events:
                continue

            if line.lower().startswith("format:"):
                fields = [field.strip().lower() for field in line.split(":", 1)[1].split(",")]
                continue

            if not line.lower().startswith(self.dialogue_prefix.lower()) or not fields:
                continue

            values = line.split(":", 1)[1].strip().split(",", len(fields) - 1)
            if len(values) < len(fields):
                continue

            row = {field: values[position].strip() for position, field in enumerate(fields)}
            if "start" not in row or "end" not in row or "text" not in row:
                continue

            text = self._clean_dialogue_text(row["text"])
            _add_loaded_segment(
                document,
                text,
                _parse_ass_timestamp(row["start"]),
                _parse_ass_timestamp(row["end"]),
            )

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        for segment in document.segments:
            text = self._escape_dialogue_text(segment.text)
            lines.append(
                "Dialogue: 0,"
                f"{_format_ass_timestamp(segment.start_time)},"
                f"{_format_ass_timestamp(segment.end_time)},"
                f"Default,,0,0,0,,{text}"
            )
        return "\n".join(lines) + "\n"

    def _clean_dialogue_text(self, text: str) -> str:
        text = re.sub(r"\{[^}]*\}", "", text)
        return text.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ").strip()

    def _escape_dialogue_text(self, text: str) -> str:
        return text.replace("\n", "\\N")


class SSAAdapter(ASSAdapter):
    format_name = "ssa"
    extensions = (".ssa",)


class SUBAdapter(SubtitleFormatAdapter):
    format_name = "sub"
    extensions = (".sub",)

    microdvd_pattern = re.compile(r"^\{(\d+)\}\{(\d+)\}(.*)$")
    mpl2_pattern = re.compile(r"^\[(\d+)\]\[(\d+)\](.*)$")
    subviewer_pattern = re.compile(
        r"^\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*,\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
    )

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        non_empty = [line.strip() for line in lines if line.strip()]

        if non_empty and all(self.microdvd_pattern.match(line) for line in non_empty):
            for line in non_empty:
                match = self.microdvd_pattern.match(line)
                if not match:
                    continue
                start_frame, end_frame, text = match.groups()
                _add_loaded_segment(
                    document,
                    text.replace("|", "\n"),
                    int(start_frame) / 25.0,
                    int(end_frame) / 25.0,
                )
            document.metadata["sub_format"] = "microdvd"
        elif non_empty and all(self.mpl2_pattern.match(line) for line in non_empty):
            for line in non_empty:
                match = self.mpl2_pattern.match(line)
                if not match:
                    continue
                start_tenths, end_tenths, text = match.groups()
                _add_loaded_segment(
                    document,
                    text.replace("|", "\n"),
                    int(start_tenths) / 10.0,
                    int(end_tenths) / 10.0,
                )
            document.metadata["sub_format"] = "mpl2"
        else:
            self._parse_subviewer(lines, document)
            document.metadata["sub_format"] = "subviewer"

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines: List[str] = []
        for segment in document.segments:
            start_time = _format_clock_timestamp(segment.start_time)[:-1]
            end_time = _format_clock_timestamp(segment.end_time)[:-1]
            lines.append(f"{start_time},{end_time}")
            lines.extend(segment.text.split("\n"))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _parse_subviewer(self, lines: List[str], document: SubtitleDocument) -> None:
        index = 0
        while index < len(lines):
            match = self.subviewer_pattern.match(lines[index])
            if not match:
                index += 1
                continue

            start_time = _parse_clock_timestamp(match.group(1))
            end_time = _parse_clock_timestamp(match.group(2))
            index += 1
            text_lines: List[str] = []
            while index < len(lines) and lines[index].strip():
                text_lines.append(lines[index])
                index += 1
            _add_loaded_segment(document, "\n".join(text_lines), start_time, end_time)


class SBVAdapter(SubtitleFormatAdapter):
    format_name = "sbv"
    extensions = (".sbv",)

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").replace("\r", "\n").strip())
        for block in blocks:
            lines = [line for line in block.split("\n") if line.strip()]
            if len(lines) < 2 or "," not in lines[0]:
                continue

            start_text, end_text = lines[0].split(",", 1)
            _add_loaded_segment(
                document,
                "\n".join(lines[1:]),
                _parse_clock_timestamp(start_text),
                _parse_clock_timestamp(end_text),
            )

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines: List[str] = []
        for segment in document.segments:
            lines.append(f"{_format_clock_timestamp(segment.start_time)},{_format_clock_timestamp(segment.end_time)}")
            lines.extend(segment.text.split("\n"))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


class LRCAdapter(SubtitleFormatAdapter):
    format_name = "lrc"
    extensions = (".lrc",)

    line_pattern = re.compile(r"^((?:\[\d+:\d{2}(?:[.:]\d{1,3})?\])+)(.*)$")
    timestamp_pattern = re.compile(r"\[(\d+:\d{2}(?:[.:]\d{1,3})?)\]")

    def parse(self, content: str, source_file: Optional[str] = None) -> SubtitleDocument:
        document = SubtitleDocument(format=self.format_name, source_file=source_file)
        timed_lines: List[tuple[float, str]] = []

        for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw_line.strip()
            match = self.line_pattern.match(line)
            if not match:
                continue

            timestamps, text = match.groups()
            for timestamp in self.timestamp_pattern.findall(timestamps):
                timed_lines.append((_parse_lrc_timestamp(timestamp), text.strip()))

        timed_lines.sort(key=lambda item: item[0])
        for index, (start_time, text) in enumerate(timed_lines):
            end_time = timed_lines[index + 1][0] if index + 1 < len(timed_lines) else start_time + 2.0
            _add_loaded_segment(document, text, start_time, end_time)

        document.modified = False
        return document

    def serialize(self, document: SubtitleDocument) -> str:
        lines = []
        for segment in document.segments:
            text = " / ".join(line.strip() for line in segment.text.split("\n") if line.strip())
            lines.append(f"[{_format_lrc_timestamp(segment.start_time)}]{text}")
        return "\n".join(lines) + "\n"


class SubtitleFormatRegistry:
    """Lookup helpers for subtitle format adapters."""

    _adapters: Dict[str, SubtitleFormatAdapter] = {
        adapter.format_name: adapter
        for adapter in (
            SRTAdapter(),
            SMIAdapter(),
            VTTAdapter(),
            ASSAdapter(),
            SSAAdapter(),
            SUBAdapter(),
            SBVAdapter(),
            LRCAdapter(),
        )
    }

    @classmethod
    def supported_formats(cls) -> List[str]:
        return [name.upper() for name in cls._adapters]

    @classmethod
    def all_extensions(cls) -> List[str]:
        extensions: List[str] = []
        for adapter in cls._adapters.values():
            extensions.extend(adapter.extensions)
        return extensions

    @classmethod
    def get_adapter(cls, format_name: str) -> SubtitleFormatAdapter:
        normalized = format_name.lower().lstrip(".")
        if normalized not in cls._adapters:
            raise ValueError(f"Unsupported subtitle format: {format_name}")
        return cls._adapters[normalized]

    @classmethod
    def get_adapter_for_path(cls, file_path: str) -> SubtitleFormatAdapter:
        suffix = Path(file_path).suffix.lower()
        for adapter in cls._adapters.values():
            if suffix in adapter.extensions:
                return adapter
        raise ValueError(f"Unsupported subtitle file: {file_path}")


def document_to_srt_entries(document: SubtitleDocument) -> List[SRTEntry]:
    """Compatibility helper for older code that still expects SRTEntry objects."""
    entries: List[SRTEntry] = []
    for index, segment in enumerate(document.segments, start=1):
        entries.append(
            SRTEntry(
                index=index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text,
            )
        )
    return entries
