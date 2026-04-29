"""
Transcription panel.

The panel now treats a SubtitleDocument as its source of truth so loaded subtitle
files and live transcription share the same editing path.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor, QTextDocument, QSyntaxHighlighter
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.subtitle_format_adapters import SubtitleFormatRegistry, document_to_srt_entries
from src.models.srt_entry import SRTEntry
from src.models.subtitle_document import SubtitleDocument
from src.models.subtitle_segment import SegmentSource, SubtitleSegment
from src.models.transcription_segment import TranscriptionSegment
from src.utils.timestamp_utils import format_time_display


class TextDialogSettings:
    """Shared settings keys for edit/find dialogs."""

    EDIT_SIZE = "transcription_dialog/edit_size"
    FIND_SIZE = "transcription_dialog/find_size"


def _settings_size(settings: QSettings, key: str, default: QSize) -> QSize:
    size = settings.value(key, default)
    return size if isinstance(size, QSize) else default


class TranscriptionEditDialog(QDialog):
    """Resizable transcription edit dialog with persistent font settings."""

    def __init__(self, text: str, font: QFont, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWindowTitle("Edit Subtitle")
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlainText(text)
        self.text_edit.document().setDefaultFont(font)
        self.text_edit.setFont(font)
        layout.addWidget(self.text_edit, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(_settings_size(self.settings, TextDialogSettings.EDIT_SIZE, QSize(640, 360)))
        self.text_edit.setFocus()

    def text(self) -> str:
        return self.text_edit.toPlainText()

    def _save_settings(self):
        self.settings.setValue(TextDialogSettings.EDIT_SIZE, self.size())

    def accept(self):
        self._save_settings()
        super().accept()

    def reject(self):
        self._save_settings()
        super().reject()


class FindTextDialog(QDialog):
    """Resizable find dialog with persistent font settings."""

    def __init__(self, font: QFont, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWindowTitle("Find Text")
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Search for:"))
        self.search_input = QLineEdit()
        self.search_input.setFont(font)
        layout.addWidget(self.search_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(_settings_size(self.settings, TextDialogSettings.FIND_SIZE, QSize(420, 160)))
        self.search_input.setFocus()

    def text(self) -> str:
        return self.search_input.text().strip()

    def _save_settings(self):
        self.settings.setValue(TextDialogSettings.FIND_SIZE, self.size())

    def accept(self):
        self._save_settings()
        super().accept()

    def reject(self):
        self._save_settings()
        super().reject()


class SRTSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for compact subtitle previews."""

    def __init__(self, parent: Optional[QTextDocument] = None):
        super().__init__(parent)
        self.timestamp_format = QTextCharFormat()
        self.timestamp_format.setForeground(QColor(100, 150, 200))
        self.index_format = QTextCharFormat()
        self.index_format.setForeground(QColor(150, 150, 100))

    def highlightBlock(self, text: str):
        if text.strip().isdigit():
            self.setFormat(0, len(text), self.index_format)

        timestamp_pattern = r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}"
        for match in re.finditer(timestamp_pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.timestamp_format)


class TranscriptionPanel(QWidget):
    """Editor-first subtitle panel backed by SubtitleDocument."""

    transcription_updated = pyqtSignal(str, float, float)
    correction_made = pyqtSignal(dict)
    export_requested = pyqtSignal(str)
    seek_requested = pyqtSignal(float)
    font_preferences_changed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = SubtitleDocument(format="srt", language="auto")
        self.display_mode = "live"
        self.loaded_from_srt = False
        self.current_time = 0.0
        self.current_line_index = -1
        self.subtitle_format = "SRT"
        self._syncing_table = False
        self.external_selection_range: Optional[tuple[float, float]] = None
        self.correction_collector = None
        self.database_manager = None

        self.setup_ui()
        self.setup_connections()
        self._apply_editor_font(self._selected_editor_font())
        self._refresh_all_views()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.mode_label = QLabel()
        toolbar.addWidget(self.mode_label)

        toolbar.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "SMI", "VTT", "ASS", "SSA", "SUB", "LRC"])
        toolbar.addWidget(self.format_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find subtitle text, timestamp, or segment number")
        toolbar.addWidget(self.search_input, 1)

        self.remove_btn = QPushButton("Remove")
        self.sync_btn = QPushButton("Sync Offset")
        self.clear_btn = QPushButton("Clear")
        for button in (self.remove_btn, self.sync_btn, self.clear_btn):
            toolbar.addWidget(button)

        toolbar.addWidget(QLabel("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Consolas"))
        toolbar.addWidget(self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 36)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(11)
        toolbar.addWidget(self.font_size_spin)

        self.stats_label = QLabel("Segments: 0 | Words: 0")
        toolbar.addWidget(self.stats_label)
        layout.addLayout(toolbar)

        self.segment_table = QTableWidget(0, 5)
        self.segment_table.setHorizontalHeaderLabels(["#", "Start", "End", "Text", "Status"])
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.segment_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.segment_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.segment_table.setAlternatingRowColors(True)
        self.segment_table.setWordWrap(True)
        self.segment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.segment_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.setStyleSheet(
            "QTableWidget { background: #181c24; alternate-background-color: #141923; color: #e8ecf5; gridline-color: #2b3443; }"
            "QHeaderView::section { background: #202737; color: #d8e0f0; padding: 6px; border: 0; }"
            "QTableWidget::item:selected { background: #0f84e8; color: white; }"
        )
        layout.addWidget(self.segment_table, 4)

        self.preview_tabs = QTabWidget()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.highlighter = SRTSyntaxHighlighter(self.text_edit.document())
        self.preview_tabs.addTab(self.text_edit, "Document View")

        self.raw_srt_preview = QTextEdit()
        self.raw_srt_preview.setReadOnly(True)
        self.preview_tabs.addTab(self.raw_srt_preview, "Raw SRT")

        self.raw_smi_preview = QTextEdit()
        self.raw_smi_preview.setReadOnly(True)
        self.preview_tabs.addTab(self.raw_smi_preview, "Raw SMI")

        editor_box = QGroupBox("Selected Subtitle")
        editor_layout = QVBoxLayout(editor_box)
        self.selection_label = QLabel("Range: --")
        editor_layout.addWidget(self.selection_label)
        self.segment_editor = QTextEdit()
        self.segment_editor.setAcceptRichText(False)
        self.segment_editor.setMinimumHeight(140)
        editor_layout.addWidget(self.segment_editor)

        editor_actions = QHBoxLayout()
        self.save_edit_btn = QPushButton("Save Edit")
        self.insert_omitted_btn = QPushButton("Insert Omitted")
        self.jump_to_start_btn = QPushButton("Jump To Start")
        self.use_range_btn = QPushButton("Use Edited Subtitle Duration")
        editor_actions.addWidget(self.save_edit_btn)
        editor_actions.addWidget(self.insert_omitted_btn)
        editor_actions.addWidget(self.jump_to_start_btn)
        editor_actions.addWidget(self.use_range_btn)
        editor_actions.addStretch()
        editor_layout.addLayout(editor_actions)

        bottom_split = QSplitter(Qt.Orientation.Horizontal)
        bottom_split.addWidget(editor_box)
        bottom_split.addWidget(self.preview_tabs)
        bottom_split.setSizes([420, 480])
        layout.addWidget(bottom_split, 3)

        status_layout = QHBoxLayout()
        self.position_label = QLabel("Position: 00:00:00")
        self.selected_range_label = QLabel("Selected range: --")
        self.word_count_label = QLabel("")
        status_layout.addWidget(self.position_label)
        status_layout.addStretch()
        status_layout.addWidget(self.selected_range_label)
        status_layout.addStretch()
        status_layout.addWidget(self.word_count_label)
        layout.addLayout(status_layout)

        self.set_mode("live")
        self.set_dark_theme(True)

    def setup_connections(self):
        self.remove_btn.clicked.connect(self.remove_selected_segment)
        self.sync_btn.clicked.connect(self.adjust_sync)
        self.clear_btn.clicked.connect(self.clear_all)
        self.font_combo.currentFontChanged.connect(self._on_toolbar_font_changed)
        self.font_size_spin.valueChanged.connect(self._on_toolbar_font_changed)
        self.segment_table.itemSelectionChanged.connect(self._sync_editor_from_selection)
        self.save_edit_btn.clicked.connect(self.save_selected_edit)
        self.insert_omitted_btn.clicked.connect(self.insert_omitted_segment)
        self.jump_to_start_btn.clicked.connect(self.jump_to_selected_start)
        self.use_range_btn.clicked.connect(self.copy_selected_range_to_status)
        self.search_input.returnPressed.connect(self.find_text)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

    def set_correction_collector(self, collector):
        self.correction_collector = collector

    def set_database_manager(self, db_manager):
        self.database_manager = db_manager

    def set_mode(self, mode: str):
        self.display_mode = mode
        if mode == "live":
            self.mode_label.setText("LIVE MODE")
            self.mode_label.setStyleSheet(
                "QLabel { background-color: #2d5a2d; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }"
            )
        else:
            self.mode_label.setText("SUBTITLE MODE")
            self.mode_label.setStyleSheet(
                "QLabel { background-color: #5a2d2d; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }"
            )

    def load_subtitle_document(self, document: SubtitleDocument):
        self.document = document
        self.document.language = self.document.language or self._current_language()
        self.subtitle_format = self.document.format.upper()
        self.loaded_from_srt = self.document.format.lower() == "srt"
        self.set_mode("srt")
        self._refresh_all_views()

    def load_subtitle_file(self, file_path: str):
        adapter = SubtitleFormatRegistry.get_adapter_for_path(file_path)
        self.load_subtitle_document(adapter.import_file(file_path))

    def add_transcription(
        self,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float = 0.8,
        language: str = None,
    ):
        language = language or self._current_language()
        update_index = self._find_document_segment_update_index(start_time, end_time)
        source = SegmentSource.LIVE if self.display_mode == "live" else SegmentSource.RETRANSCRIBED

        if update_index is not None:
            segment = self.document.segments[update_index]
            segment.text = text
            segment.start_time = start_time
            segment.end_time = end_time
            segment.confidence = confidence
            segment.language = language
            if segment.source in (SegmentSource.LOADED, SegmentSource.EDITED):
                segment.source = SegmentSource.RETRANSCRIBED
            else:
                segment.source = source
        else:
            update_index = self._insert_segment_sorted(
                SubtitleSegment(
                    text=text,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=confidence,
                    language=language,
                    source=source,
                )
            )

        self.document.format = self._normalized_format(self.format_combo.currentText())
        self.subtitle_format = self.document.format.upper()
        self._refresh_all_views(select_index=update_index)
        self.transcription_updated.emit(text, start_time, end_time)

    def add_sentence(
        self,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float = 0.8,
        language: str = None,
    ):
        self.add_transcription(text, start_time, end_time, confidence, language)

    def test_add_transcription(self):
        self.add_transcription(
            "TEST: This is a test transcription. If you see this text, the transcription panel is working correctly!",
            0.0,
            5.0,
            0.95,
        )

    def reset_for_new_file(self):
        self.document = SubtitleDocument(format="srt", language=self._current_language())
        self.loaded_from_srt = False
        self.current_line_index = -1
        self.set_mode("live")
        self._refresh_all_views()

    def load_srt(self, srt_entries: List[SRTEntry]):
        document = SubtitleDocument(format="srt", language=self._current_language())
        for entry in srt_entries:
            document.segments.append(
                SubtitleSegment(
                    index=entry.index,
                    text=entry.text,
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    confidence=1.0,
                    language=self._current_language(),
                    source=SegmentSource.LOADED,
                )
            )
        document.modified = False
        self.load_subtitle_document(document)

    def update_position(self, position_seconds: float):
        self.current_time = position_seconds
        self.position_label.setText(f"Position: {format_time_display(position_seconds)}")

        active_index = -1
        for index, segment in enumerate(self.document.segments):
            if segment.start_time <= position_seconds <= segment.end_time:
                active_index = index
                break

        if active_index != self.current_line_index:
            self.current_line_index = active_index
            if active_index >= 0:
                self._select_row(active_index)
                self._highlight_document_row(active_index)
            else:
                self._clear_highlight()

    def edit_current_line(self):
        index = self.current_line_index if self.current_line_index >= 0 else self.segment_table.currentRow()
        if not (0 <= index < len(self.document.segments)):
            return

        segment = self.document.segments[index]
        dialog = TranscriptionEditDialog(segment.text, self._selected_editor_font(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_text = dialog.text().strip()
        if not new_text or new_text == segment.text:
            return

        self._apply_segment_edit(index, new_text)

    def save_selected_edit(self):
        row = self.segment_table.currentRow()
        if not (0 <= row < len(self.document.segments)):
            return

        new_text = self.segment_editor.toPlainText().strip()
        if not new_text:
            return

        self._apply_segment_edit(row, new_text)

    def insert_omitted_segment(self):
        new_text = self.segment_editor.toPlainText().strip()
        if not new_text:
            QMessageBox.information(self, "Missing Text", "Enter the omitted subtitle text before inserting it.")
            return

        start_time, end_time = self._suggest_insertion_range()
        language = self._current_language()
        insert_index = self._insert_segment_sorted(
            SubtitleSegment(
                text=new_text,
                start_time=start_time,
                end_time=end_time,
                confidence=0.0,
                language=language,
                source=SegmentSource.EDITED,
            )
        )
        self._store_correction(
            "",
            new_text,
            confidence=0.0,
            start_time=start_time,
            end_time=end_time,
            file_path=self._current_file_path(),
            language=language,
        )
        self._refresh_all_views(select_index=insert_index)

    def jump_to_selected_start(self):
        row = self.segment_table.currentRow()
        if 0 <= row < len(self.document.segments):
            self.seek_requested.emit(self.document.segments[row].start_time)

    def get_selected_segment_range(self) -> Optional[tuple[float, float]]:
        row = self.segment_table.currentRow()
        if 0 <= row < len(self.document.segments):
            segment = self.document.segments[row]
            return segment.start_time, segment.end_time
        return None

    def set_external_selection_range(self, start_time: float, end_time: float):
        self.external_selection_range = (start_time, end_time)
        range_text = f"{format_time_display(start_time)} - {format_time_display(end_time)}"
        self.selected_range_label.setText(f"Selected range: {range_text}")

    def clear_external_selection_range(self):
        self.external_selection_range = None
        selected_range = self.get_selected_segment_range()
        if selected_range:
            self.set_external_selection_range(*selected_range)
            self.external_selection_range = None
        else:
            self.selected_range_label.setText("Selected range: --")

    def remove_selected_segment(self):
        row = self.segment_table.currentRow()
        if not (0 <= row < len(self.document.segments)):
            return

        del self.document.segments[row]
        self.document.modified = True
        self.document.modified_at = datetime.now().isoformat()

        if not self.document.segments:
            self.current_line_index = -1
            self._refresh_all_views()
            return

        next_index = min(row, len(self.document.segments) - 1)
        self.current_line_index = next_index
        self._refresh_all_views(select_index=next_index)

    def copy_selected_range_to_status(self):
        selected_range = self.get_selected_segment_range()
        if selected_range:
            range_text = f"{format_time_display(selected_range[0])} - {format_time_display(selected_range[1])}"
            self.selection_label.setText(f"Range: {range_text}")
            self.set_external_selection_range(*selected_range)
            QApplication.clipboard().setText(range_text)

    def find_text(self):
        query = self.search_input.text().strip()
        if not query:
            dialog = FindTextDialog(self._selected_editor_font(), self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            query = dialog.text()

        if not query:
            return

        lower_query = query.lower()
        for row, segment in enumerate(self.document.segments):
            haystacks = [
                segment.text.lower(),
                format_time_display(segment.start_time).lower(),
                format_time_display(segment.end_time).lower(),
                str(row + 1),
            ]
            if any(lower_query in value for value in haystacks):
                self._select_row(row)
                self._highlight_document_row(row)
                return

        cursor = self.text_edit.document().find(query)
        if not cursor.isNull():
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
            return

        QMessageBox.information(self, "Not Found", f"Text '{query}' not found.")

    def export_srt(self, file_path: str = None):
        if isinstance(file_path, bool):
            file_path = None

        if not self.document.segments:
            QMessageBox.warning(self, "No Content", "No subtitle content to export.")
            return

        target_format = self._preferred_export_format()
        if file_path is None:
            all_extensions = " ".join(f"*{extension}" for extension in SubtitleFormatRegistry.all_extensions())
            format_filters = ";;".join(
                f"{format_name} Subtitle (*.{format_name.lower()})"
                for format_name in SubtitleFormatRegistry.supported_formats()
            )
            filters = f"Subtitle Files ({all_extensions});;{format_filters};;All Files (*.*)"
            default_name = f"{self._suggested_export_stem()}.{target_format}"
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Subtitle File", default_name, filters)

        if not file_path:
            return

        try:
            adapter = SubtitleFormatRegistry.get_adapter_for_path(file_path)
        except ValueError:
            adapter = SubtitleFormatRegistry.get_adapter(target_format)
            file_path = f"{file_path}.{adapter.format_name}"

        try:
            adapter.export_file(file_path, self.document)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Error saving subtitle file:\n{exc}")
            return

        QMessageBox.information(self, "Export Successful", f"Subtitle file saved to:\n{file_path}")
        self.export_requested.emit(file_path)

    def adjust_sync(self):
        offset_ms, ok = QInputDialog.getInt(
            self,
            "Sync Adjustment",
            "Adjust timestamps by (milliseconds):\nPositive = forward, Negative = backward",
            0,
            -5000,
            5000,
            100,
        )
        if not ok or offset_ms == 0:
            return

        offset_seconds = offset_ms / 1000.0
        for segment in self.document.segments:
            segment.start_time = max(0.0, segment.start_time + offset_seconds)
            segment.end_time = max(segment.start_time + 0.001, segment.end_time + offset_seconds)
            if segment.source == SegmentSource.LOADED:
                segment.source = SegmentSource.EDITED

        self._refresh_all_views(select_index=self.segment_table.currentRow())

    def clear_all(self):
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Are you sure you want to clear all transcription?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_for_new_file()

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def get_segments(self) -> List[TranscriptionSegment]:
        return [
            TranscriptionSegment(
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                confidence=segment.confidence,
                language=segment.language,
            )
            for segment in self.document.segments
        ]

    def get_srt_entries(self) -> List[SRTEntry]:
        return document_to_srt_entries(self.document)

    def set_font_size(self, size: int):
        font = self.text_edit.font()
        font.setPointSize(size)
        self._apply_editor_font(font)

    def set_font_family(self, family: str):
        font = self.text_edit.font()
        font.setFamily(family)
        self._apply_editor_font(font)

    def set_editor_font(self, family: str, size: int):
        self.font_combo.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.font_combo.setCurrentFont(QFont(family))
        self.font_size_spin.setValue(size)
        self.font_combo.blockSignals(False)
        self.font_size_spin.blockSignals(False)
        self._apply_editor_font(QFont(family, size))

    def set_dark_theme(self, enabled: bool = True):
        palette = self.text_edit.palette()
        if enabled:
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 35))
            palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        else:
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        for editor in (self.text_edit, self.raw_srt_preview, self.raw_smi_preview, self.segment_editor):
            editor.setPalette(palette)

    def copy_selection(self):
        if self.segment_editor.hasFocus():
            self.segment_editor.copy()
        else:
            self.text_edit.copy()

    def select_all(self):
        if self.segment_editor.hasFocus():
            self.segment_editor.selectAll()
        else:
            self.text_edit.selectAll()

    def export_as_text(self, file_path: str):
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("\n\n".join(segment.text for segment in self.document.segments).strip())

    def get_current_line_text(self) -> str:
        row = self.segment_table.currentRow()
        if 0 <= row < len(self.document.segments):
            return self.document.segments[row].text
        return self.segment_editor.toPlainText()

    def _refresh_all_views(self, select_index: Optional[int] = None):
        self._populate_segment_table()
        self._render_document_preview()
        self._render_raw_previews()
        self._update_stats()
        self._sync_format_widgets()

        if select_index is None and self.document.segments:
            select_index = min(max(self.current_line_index, 0), len(self.document.segments) - 1)
        if select_index is not None and 0 <= select_index < len(self.document.segments):
            self._select_row(select_index)
            self._highlight_document_row(select_index)
        else:
            self.segment_editor.clear()
            self.selection_label.setText("Range: --")
            self.selected_range_label.setText("Selected range: --")

    def _populate_segment_table(self):
        self._syncing_table = True
        self.segment_table.setRowCount(len(self.document.segments))
        for row, segment in enumerate(self.document.segments):
            values = [
                str(row + 1),
                self._as_srt_timestamp(segment.start_time),
                self._as_srt_timestamp(segment.end_time),
                segment.text,
                self._segment_status(segment),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 1, 2, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4:
                    item.setForeground(self._status_color(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.segment_table.setItem(row, col, item)
        self._syncing_table = False

    def _render_document_preview(self):
        lines: List[str] = []
        for segment in self.document.segments:
            lines.append(
                f"[{format_time_display(segment.start_time)} -> {format_time_display(segment.end_time)}] {self._confidence_badge(segment.confidence)}"
            )
            lines.append(segment.text)
            lines.append("")
        self.text_edit.setPlainText("\n".join(lines).rstrip())
        self._apply_editor_font(self._selected_editor_font())

    def _render_raw_previews(self):
        self.raw_srt_preview.setPlainText(
            SubtitleFormatRegistry.get_adapter("srt").serialize(self.document) if self.document.segments else ""
        )
        self.raw_smi_preview.setPlainText(
            SubtitleFormatRegistry.get_adapter("smi").serialize(self.document) if self.document.segments else ""
        )

    def _sync_editor_from_selection(self):
        if self._syncing_table:
            return

        row = self.segment_table.currentRow()
        if not (0 <= row < len(self.document.segments)):
            return

        self.current_line_index = row
        segment = self.document.segments[row]
        range_text = f"{format_time_display(segment.start_time)} - {format_time_display(segment.end_time)}"
        self.segment_editor.setPlainText(segment.text)
        self.selection_label.setText(f"Range: {range_text}")
        if self.external_selection_range is None:
            self.selected_range_label.setText(f"Selected range: {range_text}")
        self._highlight_document_row(row)

    def _apply_segment_edit(self, index: int, new_text: str):
        segment = self.document.segments[index]
        original_text = segment.text
        if original_text == new_text:
            return

        segment.text = new_text
        segment.source = SegmentSource.EDITED
        self.document.modified = True
        self.document.modified_at = datetime.now().isoformat()
        self._store_correction(
            original_text,
            new_text,
            confidence=max(segment.confidence, 0.6),
            start_time=segment.start_time,
            end_time=segment.end_time,
            file_path=self._current_file_path(),
            language=segment.language or self._current_language(),
        )
        self._refresh_all_views(select_index=index)

    def _store_correction(
        self,
        original: str,
        corrected: str,
        confidence: float,
        start_time: float = 0,
        end_time: float = 0,
        file_path: str = None,
        language: str = None,
    ):
        if not self.database_manager or original == corrected:
            return

        correction_data = {
            "audio_hash": f"correction_{datetime.now().timestamp()}",
            "original_text": original,
            "corrected_text": corrected,
            "confidence": confidence,
            "language": language or self._current_language(),
            "file_path": file_path or self._current_file_path() or "",
            "start_time": start_time,
            "end_time": end_time,
        }

        result = False
        if self.correction_collector:
            result = self.correction_collector.collect_correction(
                None,
                original,
                corrected,
                confidence,
                correction_data["language"],
                correction_data["file_path"],
                start_time,
                end_time,
            )

        if not result and self.database_manager:
            self.database_manager.add_correction(correction_data)
            result = True

        if result:
            pending_count = (
                self.correction_collector.get_pending_count()
                if self.correction_collector
                else self.database_manager.get_statistics().get("pending_corrections", 0)
            )
            self.correction_made.emit({**correction_data, "stored": True, "pending_count": pending_count})

    def _find_document_segment_update_index(self, start_time: float, end_time: float) -> Optional[int]:
        if not self.document.segments:
            return None

        if 0 <= self.current_line_index < len(self.document.segments):
            segment = self.document.segments[self.current_line_index]
            if self._ranges_match(segment.start_time, segment.end_time, start_time, end_time):
                return self.current_line_index

        best_index = None
        best_overlap = 0.0
        for index, segment in enumerate(self.document.segments):
            overlap_start = max(start_time, segment.start_time)
            overlap_end = min(end_time, segment.end_time)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_index = index

        if best_index is not None and best_overlap > 0:
            return best_index
        return None

    def _insert_segment_sorted(self, segment: SubtitleSegment) -> int:
        insert_at = len(self.document.segments)
        for index, existing in enumerate(self.document.segments):
            if segment.start_time < existing.start_time:
                insert_at = index
                break
        self.document.insert_segment(insert_at, segment)
        return insert_at

    def _suggest_insertion_range(self) -> tuple[float, float]:
        row = self.segment_table.currentRow()
        if 0 <= row < len(self.document.segments):
            previous_segment = self.document.segments[row]
            next_segment = self.document.segments[row + 1] if row + 1 < len(self.document.segments) else None
            start_time = max(previous_segment.end_time, self.current_time if self.current_time > previous_segment.end_time else previous_segment.end_time)

            if next_segment and start_time < next_segment.start_time:
                end_time = next_segment.start_time
            else:
                fallback_duration = max(previous_segment.duration(), 1.5)
                end_time = start_time + fallback_duration
                if next_segment:
                    end_time = min(end_time, max(start_time + 0.2, next_segment.start_time))
            return start_time, max(start_time + 0.2, end_time)

        if self.document.segments:
            insert_at = self._find_insertion_index_for_time(self.current_time)
            previous_segment = self.document.segments[insert_at - 1] if insert_at > 0 else None
            next_segment = self.document.segments[insert_at] if insert_at < len(self.document.segments) else None
            start_time = self.current_time
            if previous_segment:
                start_time = max(start_time, previous_segment.end_time)
            if next_segment:
                end_time = max(start_time + 0.2, next_segment.start_time)
            else:
                end_time = start_time + max(previous_segment.duration(), 1.5) if previous_segment else start_time + 2.0
            return start_time, max(start_time + 0.2, end_time)

        start_time = max(0.0, self.current_time)
        return start_time, start_time + 2.0

    def _find_insertion_index_for_time(self, time_value: float) -> int:
        for index, segment in enumerate(self.document.segments):
            if time_value < segment.start_time:
                return index
        return len(self.document.segments)

    @staticmethod
    def _ranges_match(existing_start: float, existing_end: float, new_start: float, new_end: float) -> bool:
        if not (new_end < existing_start or new_start > existing_end):
            return True
        return abs(existing_start - new_start) <= 0.35 and abs(existing_end - new_end) <= 0.35

    def _segment_status(self, segment: SubtitleSegment) -> str:
        if segment.flagged_for_training:
            return "Queued"
        if segment.is_reviewed:
            return "Reviewed"
        if segment.source == SegmentSource.LOADED:
            return "Loaded"
        if segment.source == SegmentSource.RETRANSCRIBED:
            return "Retranscribed"
        if segment.source == SegmentSource.EDITED:
            return "Edited"
        return "AI Draft"

    def _status_color(self, status: str) -> QColor:
        return {
            "Loaded": QColor("#31c46d"),
            "Reviewed": QColor("#31c46d"),
            "Retranscribed": QColor("#59a7ff"),
            "Edited": QColor("#d487ff"),
            "Queued": QColor("#ff8d5e"),
            "AI Draft": QColor("#f6c244"),
        }.get(status, QColor("#d8e0f0"))

    def _confidence_badge(self, confidence: float) -> str:
        if confidence >= 0.8:
            return "[high]"
        if confidence >= 0.5:
            return "[mid]"
        return "[low]"

    def _highlight_document_row(self, row: int):
        block = self.text_edit.document().findBlockByNumber(row * 3 + 1)
        if not block.isValid():
            return
        cursor = self.text_edit.textCursor()
        cursor.setPosition(block.position())
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def _clear_highlight(self):
        cursor = self.text_edit.textCursor()
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)

    def _select_row(self, row: int):
        self._syncing_table = True
        self.segment_table.selectRow(row)
        self._syncing_table = False
        self._sync_editor_from_selection()

    def _update_stats(self):
        stats = self.document.get_stats()
        self.stats_label.setText(f"Segments: {stats['segment_count']} | Words: {stats['word_count']}")
        self.word_count_label.setText(f"Chars: {stats['character_count']}")

    def _sync_format_widgets(self):
        display_format = self.document.format.upper() if self.document.format else "SRT"
        self.subtitle_format = display_format
        self.format_combo.blockSignals(True)
        if self.format_combo.findText(display_format) >= 0:
            self.format_combo.setCurrentText(display_format)
        self.format_combo.blockSignals(False)

    def _on_format_changed(self, value: str):
        normalized = self._normalized_format(value)
        self.document.format = normalized
        self.subtitle_format = normalized.upper()
        self.loaded_from_srt = normalized == "srt"
        self._render_raw_previews()

    def _preferred_export_format(self) -> str:
        normalized = self._normalized_format(self.format_combo.currentText())
        try:
            SubtitleFormatRegistry.get_adapter(normalized)
            return normalized
        except ValueError:
            return "srt"

    def _selected_editor_font(self) -> QFont:
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size_spin.value())
        return font

    def _apply_editor_font(self, font: QFont):
        for editor in (self.text_edit, self.raw_srt_preview, self.raw_smi_preview, self.segment_editor):
            editor.document().setDefaultFont(font)
            editor.setFont(font)
            editor.setCurrentFont(font)

    def _on_toolbar_font_changed(self):
        family = self.font_combo.currentFont().family()
        size = self.font_size_spin.value()
        self._apply_editor_font(QFont(family, size))
        self.font_preferences_changed.emit(family, size)

    def _current_language(self) -> str:
        parent = self.parent()
        while parent:
            if hasattr(parent, "transcriber") and parent.transcriber:
                language = getattr(parent.transcriber, "language", None)
                if language:
                    return language
            if hasattr(parent, "current_language") and parent.current_language:
                return parent.current_language
            if hasattr(parent, "config") and parent.config:
                language = parent.config.get("language", None)
                if language:
                    return language
            parent = parent.parent()
        return "auto"

    def _current_file_path(self) -> Optional[str]:
        parent = self.parent()
        while parent:
            if hasattr(parent, "current_file") and parent.current_file:
                return parent.current_file.path
            parent = parent.parent()
        return None

    def _suggested_export_stem(self) -> str:
        current_file_path = self._current_file_path()
        if current_file_path:
            return Path(current_file_path).stem
        if self.document.source_file:
            return Path(self.document.source_file).stem
        return "subtitle_export"

    @staticmethod
    def _normalized_format(value: str) -> str:
        return value.lower().strip(".")

    @staticmethod
    def _as_srt_timestamp(seconds: float) -> str:
        whole_seconds = int(seconds)
        milliseconds = int(round((seconds - whole_seconds) * 1000))
        hours = whole_seconds // 3600
        minutes = (whole_seconds % 3600) // 60
        secs = whole_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
