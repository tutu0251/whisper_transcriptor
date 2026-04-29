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


class SubtitleFormatRegistry:
    """Lookup helpers for subtitle format adapters."""

    _adapters: Dict[str, SubtitleFormatAdapter] = {
        adapter.format_name: adapter
        for adapter in (SRTAdapter(), SMIAdapter())
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
