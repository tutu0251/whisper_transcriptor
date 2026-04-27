"""
Mock subtitle-editor-centered app for UX validation.

This is intentionally a non-production mockup that lets us test:
- subtitle-editor-first layout
- SRT / SMI aware workflow
- transcription tools as supporting controls
- fine-tuning tools as a side workflow
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import List

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QCheckBox,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


@dataclass
class MockSubtitleSegment:
    index: int
    start: str
    end: str
    text: str
    speaker: str = ""
    status: str = "Edited"


def build_mock_segments() -> List[MockSubtitleSegment]:
    return [
        MockSubtitleSegment(1, "00:00:02,184", "00:00:05,184", "簡単に最初に復習をして", "Narrator", "Aligned"),
        MockSubtitleSegment(2, "00:00:05,280", "00:00:08,278", "ご期待どおり", "Narrator", "Needs review"),
        MockSubtitleSegment(3, "00:00:08,339", "00:00:11,339", "とそれはもちろん現語的情報を伝える", "Narrator", "AI draft"),
        MockSubtitleSegment(4, "00:00:11,400", "00:00:14,400", "と言うことがひとつの重要なもく的に なんでありますが同時に", "Speaker A", "Edited"),
        MockSubtitleSegment(5, "00:00:14,496", "00:00:17,495", "さらにご情報をそして日編ご情報", "Speaker A", "Edited"),
        MockSubtitleSegment(6, "00:00:17,556", "00:00:20,556", "この3分方はフィジサカセンスによるものです", "Speaker B", "Queued"),
        MockSubtitleSegment(7, "00:00:20,617", "00:00:23,617", "そして、プラギング情報というのは、", "Speaker B", "Aligned"),
        MockSubtitleSegment(8, "00:00:23,710", "00:00:26,710", "とてもいいですね。", "Speaker B", "Edited"),
    ]


class MockWaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.samples = [random.uniform(-1.0, 1.0) * (0.4 + 0.6 * random.random()) for _ in range(240)]
        self.duration_seconds = 35.0
        self.selection_start = 6.0
        self.selection_end = 15.0
        self.drag_mode = None
        self.handle_threshold_px = 8

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#15171d"))

        width = self.width()
        height = self.height()
        mid = height / 2

        painter.setPen(QColor("#2b3240"))
        for x in range(0, width, max(1, width // 7)):
            painter.drawLine(x, 0, x, height)

        painter.setPen(QColor("#0f84e8"))
        step = max(1, width / max(1, len(self.samples)))
        for i, amp in enumerate(self.samples):
            x = int(i * step)
            bar = amp * (height * 0.38)
            painter.drawLine(x, int(mid - bar), x, int(mid + bar))

        start_x = self._time_to_x(self.selection_start)
        end_x = self._time_to_x(self.selection_end)
        if end_x < start_x:
            start_x, end_x = end_x, start_x

        painter.fillRect(QRectF(start_x, 0, max(2, end_x - start_x), height), QColor(36, 78, 122, 70))
        painter.fillRect(QRectF(start_x, 0, 3, height), QColor("#ffd24a"))
        painter.fillRect(QRectF(end_x, 0, 3, height), QColor("#ff6b6b"))

        painter.setPen(QColor("#6d7688"))
        painter.setFont(QFont("Consolas", 9))
        for second in range(0, 36, 5):
            x = int((second / 35.0) * max(1, width - 40))
            painter.drawText(x + 4, height - 8, f"00:{second:02d}")

        painter.setPen(QColor("#dce8ff"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            10,
            18,
            f"Selection: {self._format_seconds(self.selection_start)} - {self._format_seconds(self.selection_end)}",
        )

    def mousePressEvent(self, event):
        x = event.position().x()
        start_x = self._time_to_x(self.selection_start)
        end_x = self._time_to_x(self.selection_end)

        if abs(x - start_x) <= self.handle_threshold_px:
            self.drag_mode = "start"
        elif abs(x - end_x) <= self.handle_threshold_px:
            self.drag_mode = "end"
        elif start_x < x < end_x:
            self.drag_mode = "move"
            self.drag_offset = self._x_to_time(x) - self.selection_start
        else:
            clicked_time = self._x_to_time(x)
            self.selection_start = max(0.0, clicked_time - 1.5)
            self.selection_end = min(self.duration_seconds, clicked_time + 1.5)
            self.drag_mode = "end"
        self.update()

    def mouseMoveEvent(self, event):
        if not self.drag_mode:
            return

        current_time = self._x_to_time(event.position().x())
        if self.drag_mode == "start":
            self.selection_start = max(0.0, min(current_time, self.selection_end - 0.2))
        elif self.drag_mode == "end":
            self.selection_end = min(self.duration_seconds, max(current_time, self.selection_start + 0.2))
        elif self.drag_mode == "move":
            span = self.selection_end - self.selection_start
            new_start = max(0.0, min(self.duration_seconds - span, current_time - self.drag_offset))
            self.selection_start = new_start
            self.selection_end = new_start + span
        self.update()

    def mouseReleaseEvent(self, _event):
        self.drag_mode = None

    def _time_to_x(self, seconds: float) -> float:
        return (seconds / self.duration_seconds) * max(1, self.width() - 1)

    def _x_to_time(self, x_pos: float) -> float:
        ratio = max(0.0, min(1.0, x_pos / max(1, self.width() - 1)))
        return ratio * self.duration_seconds

    @staticmethod
    def _format_seconds(value: float) -> str:
        minutes = int(value) // 60
        seconds = int(value) % 60
        millis = int(round((value - int(value)) * 10))
        return f"{minutes:02d}:{seconds:02d}.{millis}"


class MockSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(760, 580)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self.build_editor_tab(), "Editor")
        tabs.addTab(self.build_transcription_tab(), "Transcription")
        tabs.addTab(self.build_training_tab(), "Fine Tuning")
        tabs.addTab(self.build_shortcuts_tab(), "Shortcuts")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_changes)
        layout.addWidget(buttons)

    def build_editor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        appearance = QGroupBox("Editor Appearance")
        form = QFormLayout(appearance)
        font_family = QComboBox()
        font_family.addItems(["Segoe UI", "Malgun Gothic", "Sylfaen", "Consolas"])
        font_family.setCurrentText("Segoe UI")
        form.addRow("Font", font_family)

        font_size = QSpinBox()
        font_size.setRange(8, 28)
        font_size.setValue(14)
        form.addRow("Font size", font_size)

        theme = QComboBox()
        theme.addItems(["Dark editor", "Light editor", "Subtitle editor classic"])
        form.addRow("Theme", theme)
        layout.addWidget(appearance)

        behavior = QGroupBox("Editing Behavior")
        behavior_layout = QVBoxLayout(behavior)
        for label in [
            "Enable playback-follow selection",
            "Auto-scroll to active subtitle",
            "Use timeline-first keyboard navigation",
            "Preserve subtitle-editor-compatible key flow",
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            behavior_layout.addWidget(checkbox)
        layout.addWidget(behavior)
        layout.addStretch()
        return widget

    def build_transcription_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        defaults = QGroupBox("Transcription Defaults")
        form = QFormLayout(defaults)
        model = QComboBox()
        model.addItems(["whisper-tiny", "whisper-base", "custom-ja-v2"])
        form.addRow("Default model", model)

        device = QComboBox()
        device.addItems(["Auto", "CPU", "CUDA"])
        device.setCurrentText("CUDA")
        form.addRow("Device", device)

        compute = QComboBox()
        compute.addItems(["float32", "float16", "int8"])
        compute.setCurrentText("float32")
        form.addRow("Compute type", compute)

        language = QComboBox()
        language.addItems(["AUTO", "JA", "EN", "KO"])
        form.addRow("Default language", language)

        format_pref = QComboBox()
        format_pref.addItems(["Keep source format", "Prefer SRT", "Prefer SMI"])
        form.addRow("Export preference", format_pref)

        chunk = QSpinBox()
        chunk.setRange(1, 60)
        chunk.setValue(3)
        form.addRow("Chunk seconds", chunk)
        layout.addWidget(defaults)

        helpers = QGroupBox("Assistive Features")
        helpers_layout = QVBoxLayout(helpers)
        for label, checked in [
            ("Show AI confidence markers", True),
            ("Allow re-transcribe current subtitle", True),
            ("Highlight AI-generated lines differently", True),
            ("Auto-queue corrections for fine tuning", True),
            ("Use edited subtitle duration for re-transcribe range", True),
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            helpers_layout.addWidget(checkbox)
        layout.addWidget(helpers)
        layout.addStretch()
        return widget

    def build_training_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        training = QGroupBox("Fine-Tuning Preferences")
        form = QFormLayout(training)
        mode = QComboBox()
        mode.addItems(["Manual review first", "Semi-automatic", "Background collection"])
        form.addRow("Correction workflow", mode)

        minimum = QSpinBox()
        minimum.setRange(1, 500)
        minimum.setValue(20)
        form.addRow("Min corrections to train", minimum)

        base_model = QComboBox()
        base_model.addItems(["whisper-tiny", "whisper-base", "custom-ja-v2"])
        form.addRow("Training base", base_model)
        layout.addWidget(training)

        policy = QGroupBox("Review Policy")
        policy_layout = QVBoxLayout(policy)
        for label in [
            "Only train accepted subtitle edits",
            "Keep SRT and SMI corrections in one dataset",
            "Track per-project correction history",
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            policy_layout.addWidget(checkbox)
        layout.addWidget(policy)
        layout.addStretch()
        return widget

    def build_shortcuts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        shortcuts = QGroupBox("Keyboard Workflow")
        form = QFormLayout(shortcuts)
        for label, value in [
            ("Play / Pause", "Space"),
            ("Split subtitle", "Ctrl+Enter"),
            ("Merge subtitle", "Ctrl+Backspace"),
            ("Open settings", "Ctrl+,"),
            ("Re-transcribe line", "Ctrl+R"),
            ("Fine-tune review queue", "Ctrl+Shift+T"),
        ]:
            field = QLineEdit(value)
            form.addRow(label, field)
        layout.addWidget(shortcuts)

        note = QTextEdit()
        note.setReadOnly(True)
        note.setPlainText(
            "This is a mock settings dialog.\n\n"
            "The purpose is to test whether subtitle-editor users feel comfortable with the structure, naming, and defaults before we wire the real settings backend."
        )
        layout.addWidget(note)
        return widget

    def apply_changes(self):
        QMessageBox.information(self, "Mock Settings", "Mock settings applied for prototype review.")


class MockBatchTrainingWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Training")
        self.resize(980, 720)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2b213d, stop:1 #1a3b38);"
            "border: 1px solid #4a5775; border-radius: 10px; }"
        )
        header_layout = QVBoxLayout(header)
        title = QLabel("Batch Training From Paired Media + Subtitle Folders")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: 700;")
        subtitle = QLabel(
            "Mock workflow for scanning folders, validating pairs, previewing datasets, and launching fine-tuning."
        )
        subtitle.setStyleSheet("color: #dce6f7;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        controls = QGroupBox("Batch Training Setup")
        form = QFormLayout(controls)
        folder = QLineEdit(r"D:\datasets\japanese_lessons")
        form.addRow("Training folder", folder)

        subtitle_formats = QComboBox()
        subtitle_formats.addItems(["All supported formats", "SRT + SMI priority", "SRT only", "SMI only"])
        form.addRow("Subtitle formats", subtitle_formats)

        model = QComboBox()
        model.addItems(["whisper-tiny", "whisper-base", "custom-ja-v2"])
        form.addRow("Model to train", model)

        device = QComboBox()
        device.addItems(["Auto", "CPU", "CUDA"])
        device.setCurrentText("CUDA")
        form.addRow("Device", device)

        run_mode = QComboBox()
        run_mode.addItems(["Foreground", "Background"])
        run_mode.setCurrentText("Background")
        form.addRow("Training mode", run_mode)
        layout.addWidget(controls)

        action_bar = QHBoxLayout()
        for label in [
            "Select Folder",
            "Scan Pairs",
            "Preview Dataset",
            "Validate Files",
            "Start Batch Training",
        ]:
            action_bar.addWidget(QPushButton(label))
        action_bar.addStretch()
        layout.addLayout(action_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        valid_box = QGroupBox("Valid Pairs")
        valid_layout = QVBoxLayout(valid_box)
        valid_list = QListWidget()
        for item in [
            "lesson01.mp3  <->  lesson01.srt",
            "lesson02.mp4  <->  lesson02.smi",
            "lesson03.wav  <->  lesson03.srt",
            "lesson04.mp3  <->  lesson04.smi",
        ]:
            valid_list.addItem(item)
        valid_layout.addWidget(valid_list)
        left_layout.addWidget(valid_box)

        invalid_box = QGroupBox("Issues Found")
        invalid_layout = QVBoxLayout(invalid_box)
        invalid_list = QListWidget()
        for item in [
            "lesson05.mp3  -> missing subtitle",
            "lesson06.smi  -> missing media",
            "lesson07.srt  -> parse warning",
        ]:
            invalid_list.addItem(item)
        invalid_layout.addWidget(invalid_list)
        left_layout.addWidget(invalid_box)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        summary_box = QGroupBox("Dataset Summary")
        summary_form = QFormLayout(summary_box)
        summary_form.addRow("Valid pairs", QLabel("24"))
        summary_form.addRow("Invalid items", QLabel("3"))
        summary_form.addRow("Estimated audio", QLabel("01:42:18"))
        summary_form.addRow("Detected languages", QLabel("JA, EN"))
        summary_form.addRow("Target task", QLabel("Subtitle fine-tuning"))
        summary_form.addRow("Execution mode", QLabel("Background"))
        right_layout.addWidget(summary_box)

        preview_box = QGroupBox("Training Preview")
        preview_layout = QVBoxLayout(preview_box)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(
            "Sample normalized training entries:\n\n"
            "1. lesson01.mp3\n"
            "   00:00:02,184 -> 00:00:05,184\n"
            "   簡単に最初に復習をして\n\n"
            "2. lesson02.mp4\n"
            "   00:00:08,339 -> 00:00:11,339\n"
            "   とそれはもちろん現語的情報を伝える\n"
        )
        preview_layout.addWidget(preview)
        right_layout.addWidget(preview_box, 1)

        splitter.addWidget(right)
        splitter.setSizes([420, 500])
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.clicked.connect(self.close)
        layout.addWidget(buttons)


class MediaMockPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        preview = QFrame()
        preview.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111318, stop:1 #1a1f2a);"
            " border: 1px solid #3a4253; border-radius: 8px; }"
        )
        preview_layout = QVBoxLayout(preview)
        title = QLabel("Media Preview")
        title.setStyleSheet("color: #eef2ff; font-size: 18px; font-weight: 600;")
        subtitle = QLabel("Mock player area for video/audio + subtitle timing review")
        subtitle.setStyleSheet("color: #95a0b5;")
        preview_layout.addWidget(title)
        preview_layout.addWidget(subtitle)
        preview_layout.addStretch()
        meta = QLabel("aps-smp.mp3   |   00:35 / 59:59   |   JP audio   |   Subtitle format: SRT")
        meta.setStyleSheet("color: #c6d0e1; background: rgba(20,20,28,0.55); padding: 8px; border-radius: 6px;")
        preview_layout.addWidget(meta)
        layout.addWidget(preview, 3)

        controls = QHBoxLayout()
        for label in ["Play", "Pause", "Stop", "Set In", "Set Out", "Split Here"]:
            btn = QPushButton(label)
            controls.addWidget(btn)
        controls.addStretch()
        speed = QComboBox()
        speed.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x"])
        speed.setCurrentText("1.0x")
        controls.addWidget(QLabel("Speed"))
        controls.addWidget(speed)
        layout.addLayout(controls)

        seek = QSlider(Qt.Orientation.Horizontal)
        seek.setValue(35)
        layout.addWidget(seek)

        waveform_box = QGroupBox("Waveform / Timeline")
        waveform_layout = QVBoxLayout(waveform_box)
        self.waveform = MockWaveformWidget()
        waveform_layout.addWidget(self.waveform)
        range_controls = QHBoxLayout()
        range_controls.addWidget(QLabel("Range"))
        range_controls.addWidget(QPushButton("Set In"))
        range_controls.addWidget(QPushButton("Set Out"))
        range_controls.addWidget(QPushButton("Clear Range"))
        range_controls.addStretch()
        range_controls.addWidget(QLabel("Tip: drag the yellow/red handles or drag inside selection"))
        waveform_layout.addLayout(range_controls)
        layout.addWidget(waveform_box, 2)


class SubtitleEditorMockPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments = build_mock_segments()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "SMI", "VTT", "ASS", "SSA", "SUB", "LRC"])
        self.format_combo.setCurrentText("SRT")
        top_bar.addWidget(QLabel("Subtitle Format"))
        top_bar.addWidget(self.format_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find subtitle text, speaker, or timestamp")
        top_bar.addWidget(self.search_input, 1)

        for label in ["Find", "Replace", "Add Line", "Merge", "Split", "Apply Offset"]:
            top_bar.addWidget(QPushButton(label))
        layout.addLayout(top_bar)

        self.table = QTableWidget(len(self.segments), 6)
        self.table.setHorizontalHeaderLabels(["#", "Start", "End", "Text", "Speaker", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet(
            "QTableWidget { background: #181c24; alternate-background-color: #141923; color: #e8ecf5; gridline-color: #2b3443; }"
            "QHeaderView::section { background: #202737; color: #d8e0f0; padding: 6px; border: 0; }"
            "QTableWidget::item:selected { background: #0f84e8; color: white; }"
        )
        self.populate_table()
        layout.addWidget(self.table, 4)

        bottom_split = QSplitter(Qt.Orientation.Horizontal)

        edit_box = QGroupBox("Selected Subtitle")
        edit_layout = QVBoxLayout(edit_box)
        self.editor = QTextEdit()
        self.editor.setPlainText(self.segments[0].text)
        self.editor.setMinimumHeight(120)
        edit_layout.addWidget(self.editor)
        edit_controls = QHBoxLayout()
        for label in ["Save Edit", "Re-transcribe Selection", "Use Audio Timing", "Mark Reviewed"]:
            edit_controls.addWidget(QPushButton(label))
        edit_layout.addLayout(edit_controls)
        bottom_split.addWidget(edit_box)

        preview_tabs = QTabWidget()
        preview_tabs.addTab(self.build_plain_preview(), "Editor View")
        preview_tabs.addTab(self.build_srt_preview(), "Raw SRT")
        preview_tabs.addTab(self.build_smi_preview(), "Raw SMI")
        bottom_split.addWidget(preview_tabs)

        bottom_split.setSizes([580, 460])
        layout.addWidget(bottom_split, 2)

        self.table.itemSelectionChanged.connect(self.sync_editor_from_selection)

    def populate_table(self):
        for row, segment in enumerate(self.segments):
            values = [
                str(segment.index),
                segment.start,
                segment.end,
                segment.text,
                segment.speaker,
                segment.status,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 1, 2, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5:
                    color = {
                        "Aligned": QColor("#31c46d"),
                        "Needs review": QColor("#f6c244"),
                        "AI draft": QColor("#59a7ff"),
                        "Edited": QColor("#d487ff"),
                        "Queued": QColor("#ff8d5e"),
                    }.get(value, QColor("#d8e0f0"))
                    item.setForeground(color)
                self.table.setItem(row, col, item)
        self.table.selectRow(0)

    def sync_editor_from_selection(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.segments):
            self.editor.setPlainText(self.segments[row].text)

    def build_plain_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(
            "\n\n".join(
                f"[{segment.start} -> {segment.end}]\n{segment.text}"
                for segment in self.segments
            )
        )
        layout.addWidget(preview)
        return widget

    def build_srt_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(
            "\n\n".join(
                f"{segment.index}\n{segment.start} --> {segment.end}\n{segment.text}"
                for segment in self.segments
            )
        )
        layout.addWidget(preview)
        return widget

    def build_smi_preview(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        preview = QTextEdit()
        preview.setReadOnly(True)
        smi_lines = ["<SAMI>", "<BODY>"]
        for segment in self.segments:
            start_ms = self.to_ms(segment.start)
            smi_lines.append(f"<SYNC Start={start_ms}><P Class=KRCC>{segment.text}")
        smi_lines.extend(["</BODY>", "</SAMI>"])
        preview.setPlainText("\n".join(smi_lines))
        layout.addWidget(preview)
        return widget

    @staticmethod
    def to_ms(timestamp: str) -> int:
        hh, mm, rest = timestamp.split(":")
        ss, ms = rest.split(",")
        return (
            int(hh) * 3600 * 1000
            + int(mm) * 60 * 1000
            + int(ss) * 1000
            + int(ms)
        )


class ToolSidebarMock(QWidget):
    def __init__(self, parent=None, batch_training_callback=None):
        super().__init__(parent)
        self.batch_training_callback = batch_training_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self.build_transcription_tab(), "Transcriptor")
        tabs.addTab(self.build_training_tab(), "Fine Tuner")
        tabs.addTab(self.build_project_tab(), "Project")
        layout.addWidget(tabs)

    def build_transcription_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        source_box = QGroupBox("Transcription Source")
        source_form = QFormLayout(source_box)
        model_combo = QComboBox()
        model_combo.addItems(["whisper-tiny", "whisper-base", "custom-japanese-v2"])
        source_form.addRow("Model", model_combo)
        device_combo = QComboBox()
        device_combo.addItems(["Auto", "CPU", "CUDA"])
        device_combo.setCurrentText("CUDA")
        source_form.addRow("Device", device_combo)
        compute_combo = QComboBox()
        compute_combo.addItems(["float32", "float16", "int8"])
        source_form.addRow("Compute", compute_combo)
        language = QComboBox()
        language.addItems(["AUTO", "JA", "EN", "KO"])
        source_form.addRow("Language", language)
        mode = QComboBox()
        mode.addItems(["Whole file", "Selected range", "Current subtitle"])
        source_form.addRow("Target", mode)
        layout.addWidget(source_box)

        action_box = QGroupBox("Transcription Actions")
        action_layout = QVBoxLayout(action_box)
        for label in [
            "Transcribe Whole File",
            "Transcribe Selection",
            "Re-transcribe Current Subtitle",
            "Compare With Existing Subtitle",
        ]:
            action_layout.addWidget(QPushButton(label))
        layout.addWidget(action_box)

        queue_box = QGroupBox("Recent AI Actions")
        queue_layout = QVBoxLayout(queue_box)
        queue = QListWidget()
        for text in [
            "Aligned line 1-8 using whisper-tiny",
            "Re-transcribed subtitle #2",
            "Suggested punctuation cleanup on 3 lines",
        ]:
            queue.addItem(QListWidgetItem(text))
        queue_layout.addWidget(queue)
        layout.addWidget(queue_box, 1)

        return widget

    def build_training_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stats_box = QGroupBox("Fine-Tuning Status")
        stats_form = QFormLayout(stats_box)
        stats_form.addRow("Base model", QLabel("whisper-tiny"))
        stats_form.addRow("Pending corrections", QLabel("18"))
        stats_form.addRow("Accepted edits", QLabel("42"))
        stats_form.addRow("Training set", QLabel("Japanese meeting subtitles"))
        layout.addWidget(stats_box)

        workflow_box = QGroupBox("Training Actions")
        workflow_layout = QVBoxLayout(workflow_box)
        for label in [
            "Review Pending Corrections",
            "Preview Training Examples",
            "Select Paired Folder",
            "Scan Media + Subtitle Pairs",
            "Create Fine-Tuning Dataset",
            "Choose Model To Train",
            "Run Mock Fine-Tune",
        ]:
            workflow_layout.addWidget(QPushButton(label))
        batch_window_btn = QPushButton("Open Batch Training Window")
        if self.batch_training_callback:
            batch_window_btn.clicked.connect(self.batch_training_callback)
        workflow_layout.addWidget(batch_window_btn)
        start_batch_btn = QPushButton("Start Batch Training")
        if self.batch_training_callback:
            start_batch_btn.clicked.connect(self.batch_training_callback)
        workflow_layout.addWidget(start_batch_btn)
        layout.addWidget(workflow_box)

        history_box = QGroupBox("Recent Runs")
        history_layout = QVBoxLayout(history_box)
        history = QListWidget()
        for item in [
            "Batch scan: 24 valid pairs | 3 missing subtitles",
            "2026-04-26 14:10  |  tiny-ja-v3  |  completed",
            "2026-04-25 19:42  |  tiny-ja-v2  |  completed",
            "2026-04-24 11:08  |  tiny-ja-v1  |  mock only",
        ]:
            history.addItem(item)
        history_layout.addWidget(history)
        layout.addWidget(history_box, 1)

        return widget

    def build_project_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        project_box = QGroupBox("Project Profile")
        project_form = QFormLayout(project_box)
        format_combo = QComboBox()
        format_combo.addItems(["Universal subtitle workflow", "SRT priority workflow", "SMI priority workflow"])
        project_form.addRow("Preset", format_combo)
        project_form.addRow("Default FPS", QLabel("23.976"))
        project_form.addRow("Style", QLabel("Subtitle editor compatible"))
        project_form.addRow("Hotkey mode", QLabel("Keyboard-heavy"))
        layout.addWidget(project_box)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(
            "Mockup goals:\n"
            "- Subtitle editor first\n"
            "- Same comfort level for SRT and SMI users\n"
            "- Transcription as assistive tool\n"
            "- Fine-tuning as project workflow, not separate app\n"
        )
        layout.addWidget(notes, 1)

        return widget


class MockSubtitleStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Subtitle Studio Mockup")
        self.resize(1680, 980)
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.apply_theme()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #20283a, stop:0.55 #16273f, stop:1 #1f3d3a);"
            "border: 1px solid #3e5278; border-radius: 10px; }"
        )
        hero_layout = QHBoxLayout(hero)
        hero_text = QVBoxLayout()
        title = QLabel("Subtitle Editor + Transcriptor + Fine Tuner")
        title.setStyleSheet("color: white; font-size: 26px; font-weight: 700;")
        subtitle = QLabel("Mockup only: editor-first workflow with broad subtitle-format support and assistive AI tools.")
        subtitle.setStyleSheet("color: #d6dfef; font-size: 14px;")
        hero_text.addWidget(title)
        hero_text.addWidget(subtitle)
        hero_text.addStretch()
        hero_layout.addLayout(hero_text, 1)
        pill = QLabel("UX target:\nFeels like a real subtitle editor")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setStyleSheet(
            "QLabel { background: rgba(9, 14, 24, 0.35); color: #eef4ff; border: 1px solid #6ca9ff;"
            "padding: 14px 18px; border-radius: 10px; font-weight: 600; }"
        )
        hero_layout.addWidget(pill)
        layout.addWidget(hero)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(MediaMockPane())
        splitter.addWidget(SubtitleEditorMockPane())
        splitter.addWidget(ToolSidebarMock(batch_training_callback=self.open_batch_training_window))
        splitter.setSizes([430, 860, 360])
        layout.addWidget(splitter, 1)

    def setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        for label in ["Open Media", "Open Subtitle", "Save Subtitle"]:
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, name=label: self.show_mock_message(name))
            file_menu.addAction(action)

        settings_menu = menubar.addMenu("Settings")
        settings_action = QAction("Preferences...", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(settings_action)

        training_menu = menubar.addMenu("Training")
        batch_training_action = QAction("Batch Training Window...", self)
        batch_training_action.triggered.connect(self.open_batch_training_window)
        training_menu.addAction(batch_training_action)

        view_menu = menubar.addMenu("View")
        for label in ["Editor-first layout", "Show waveform", "Show tool sidebar"]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(True)
            view_menu.addAction(action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About Mockup", self)
        about_action.triggered.connect(
            lambda: QMessageBox.information(
                self,
                "About Mockup",
                "This is a UI prototype for the subtitle-editor-centered refactor.\n\n"
                "It is intended for workflow and comfort testing, not production use.",
            )
        )
        help_menu.addAction(about_action)

    def setup_toolbar(self):
        toolbar = QToolBar("Mock Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        for label in [
            "Open Media",
            "Open Subtitle",
            "Save Subtitle",
            "Import SRT",
            "Import SMI",
            "Mock Transcribe",
            "Mock Fine-Tune",
        ]:
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, name=label: self.show_mock_message(name))
            toolbar.addAction(action)

        toolbar.addSeparator()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        toolbar.addAction(settings_action)

        batch_training_action = QAction("Batch Training", self)
        batch_training_action.triggered.connect(self.open_batch_training_window)
        toolbar.addAction(batch_training_action)

    def setup_statusbar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Mockup ready. Test the layout, editing flow, and tool grouping.")
        status.addPermanentWidget(QLabel("Format-ready: SRT / SMI"))
        status.addPermanentWidget(QLabel("Mode: Editor-first"))

    def apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #10141b;
                color: #e6ebf5;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #2c3444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                background: #171c25;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #9ec7ff;
            }
            QPushButton {
                background: #1f6fb5;
                color: white;
                border: 1px solid #3f8dd2;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #2880cc;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget, QTabWidget::pane {
                background: #161b24;
                color: #e8edf7;
                border: 1px solid #30394c;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #1a2030;
                color: #d9e1f2;
                padding: 8px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #234b77;
                color: white;
            }
            QToolBar {
                background: #171c25;
                border-bottom: 1px solid #2a3342;
                spacing: 6px;
                padding: 6px;
            }
            QStatusBar {
                background: #171c25;
                border-top: 1px solid #2a3342;
            }
            """
        )

    def show_mock_message(self, action_name: str):
        QMessageBox.information(
            self,
            "Mock Action",
            f"'{action_name}' is a mock action in this prototype.\n\n"
            "This window is for testing layout, terminology, and workflow comfort before the real refactor.",
        )

    def open_settings_dialog(self):
        dialog = MockSettingsDialog(self)
        dialog.exec()

    def open_batch_training_window(self):
        dialog = MockBatchTrainingWindow(self)
        dialog.exec()


def main():
    app = QApplication(sys.argv)
    window = MockSubtitleStudio()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
