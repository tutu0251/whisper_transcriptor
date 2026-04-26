"""
Transcription Panel Module
Real-time transcription display, SRT editing, and correction collection
"""

import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QScrollArea, QFrame, QMessageBox, QInputDialog,
    QLineEdit, QDialog, QDialogButtonBox, QSplitter, QApplication,
    QTextBrowser, QPlainTextEdit, QFontComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSettings, QSize
from PyQt6.QtGui import (
    QFont, QTextCursor, QColor, QTextCharFormat, 
    QSyntaxHighlighter, QTextDocument, QPalette,
    QTextBlockFormat
)

# Import local modules
from src.models.transcription_segment import TranscriptionSegment
from src.models.srt_entry import SRTEntry
from src.core.srt_handler import SRTHandler
from src.utils.timestamp_utils import seconds_to_srt_time, format_time_display


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
        self.setWindowTitle("Edit Transcription")
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlainText(text)
        self.text_edit.document().setDefaultFont(font)
        self.text_edit.setFont(font)
        self.text_edit.setCurrentFont(font)

        char_format = QTextCharFormat()
        char_format.setFont(font)
        self.text_edit.setCurrentCharFormat(char_format)
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

    def _save_settings(self, size_key: str):
        self.settings.setValue(size_key, self.size())

    def accept(self):
        self._save_settings(TextDialogSettings.EDIT_SIZE)
        super().accept()

    def reject(self):
        self._save_settings(TextDialogSettings.EDIT_SIZE)
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
        return self.search_input.text()

    def _save_settings(self, size_key: str):
        self.settings.setValue(size_key, self.size())

    def accept(self):
        self._save_settings(TextDialogSettings.FIND_SIZE)
        super().accept()

    def reject(self):
        self._save_settings(TextDialogSettings.FIND_SIZE)
        super().reject()


class SRTSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for SRT files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Format for timestamps
        self.timestamp_format = QTextCharFormat()
        self.timestamp_format.setForeground(QColor(100, 150, 200))
        
        # Format for indexes
        self.index_format = QTextCharFormat()
        self.index_format.setForeground(QColor(150, 150, 100))
    
    def highlightBlock(self, text: str):
        """Highlight the given block of text"""
        # Highlight index (numbers at start of line)
        if text.strip().isdigit():
            self.setFormat(0, len(text), self.index_format)
        
        # Highlight timestamps
        timestamp_pattern = r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}'
        for match in re.finditer(timestamp_pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.timestamp_format)


class TranscriptionPanel(QWidget):
    """Main transcription display and editing panel"""
    
    # Signals
    transcription_updated = pyqtSignal(str, float, float)  # text, start, end
    correction_made = pyqtSignal(dict)  # correction data
    export_requested = pyqtSignal(str)  # file path
    seek_requested = pyqtSignal(float)  # time in seconds
    font_preferences_changed = pyqtSignal(str, int)  # family, size
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Internal state
        self.segments: List[TranscriptionSegment] = []
        self.srt_entries: List[SRTEntry] = []
        self.display_mode = "live"  # "live" or "srt"
        self.current_time = 0.0
        self.current_line_index = -1
        self.correction_collector = None
        self.database_manager = None
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        
        # Mode indicator
        self.mode_label = QLabel("🎙️ LIVE MODE")
        self.mode_label.setStyleSheet("""
            QLabel {
                background-color: #2d5a2d;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)
        toolbar.addWidget(self.mode_label)
        
        toolbar.addWidget(QLabel("|"))
        
        # Edit button
        self.edit_btn = QPushButton("✏️ Edit Current")
        self.edit_btn.setToolTip("Edit current subtitle line (Ctrl+E)")
        toolbar.addWidget(self.edit_btn)
        
        # Find button
        self.find_btn = QPushButton("🔍 Find")
        self.find_btn.setToolTip("Find text in transcription (Ctrl+F)")
        toolbar.addWidget(self.find_btn)
        
        # Export button
        self.export_btn = QPushButton("💾 Export SRT")
        self.export_btn.setToolTip("Export as SRT file (Ctrl+S)")
        toolbar.addWidget(self.export_btn)
        
        # Sync button
        self.sync_btn = QPushButton("⏱️ Sync Offset")
        self.sync_btn.setToolTip("Adjust timeline offset")
        toolbar.addWidget(self.sync_btn)
        
        # Clear button
        self.clear_btn = QPushButton("🗑️ Clear")
        self.clear_btn.setToolTip("Clear all transcription")
        toolbar.addWidget(self.clear_btn)
        
        toolbar.addWidget(QLabel("|"))
        toolbar.addWidget(QLabel("Font:"))

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Consolas"))
        toolbar.addWidget(self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 36)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(11)
        toolbar.addWidget(self.font_size_spin)

        toolbar.addStretch()
        
        # Stats label
        self.stats_label = QLabel("Segments: 0 | Words: 0")
        toolbar.addWidget(self.stats_label)
        
        layout.addLayout(toolbar)
        
        # Main text area with scroll
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(False)
        self.text_edit.setFontFamily("Monospace")
        self.text_edit.setFontPointSize(11)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Apply syntax highlighter
        self.highlighter = SRTSyntaxHighlighter(self.text_edit.document())
        
        # Set dark theme for text area
        palette = self.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 35))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        self.text_edit.setPalette(palette)
        
        layout.addWidget(self.text_edit)
        
        # Bottom status bar
        status_layout = QHBoxLayout()
        
        self.position_label = QLabel("Position: 00:00:00")
        status_layout.addWidget(self.position_label)
        
        status_layout.addStretch()
        
        self.word_count_label = QLabel("")
        status_layout.addWidget(self.word_count_label)
        
        layout.addLayout(status_layout)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.edit_btn.clicked.connect(self.edit_current_line)
        self.find_btn.clicked.connect(self.find_text)
        self.export_btn.clicked.connect(lambda: self.export_srt())
        self.sync_btn.clicked.connect(self.adjust_sync)
        self.clear_btn.clicked.connect(self.clear_all)
        self.font_combo.currentFontChanged.connect(self._on_toolbar_font_changed)
        self.font_size_spin.valueChanged.connect(self._on_toolbar_font_changed)
    
    def set_correction_collector(self, collector):
        """Set the correction collector for continuous learning"""
        self.correction_collector = collector
    
    def set_database_manager(self, db_manager):
        """Set the database manager"""
        self.database_manager = db_manager
    
    def set_mode(self, mode: str):
        """Set display mode: 'live' or 'srt'"""
        self.display_mode = mode
        
        if mode == "live":
            self.mode_label.setText("🎙️ LIVE MODE")
            self.mode_label.setStyleSheet("""
                QLabel {
                    background-color: #2d5a2d;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
        else:
            self.mode_label.setText("📄 SRT MODE")
            self.mode_label.setStyleSheet("""
                QLabel {
                    background-color: #5a2d2d;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
    
    def add_transcription(self, text: str, start_time: float, end_time: float,
                          confidence: float = 0.8, language: str = None):
        """
        Add a new transcription segment in real-time
        
        Args:
            text: Transcribed text
            start_time: Start time in seconds
            end_time: End time in seconds
            confidence: Confidence score (0-1)
        """
        print(f"🔴 add_transcription called: text='{text[:50]}...', start={start_time:.1f}, end={end_time:.1f}")
        
        # Create segment
        segment = TranscriptionSegment(
            text=text,
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
            language=language or self._current_language()
        )
        self.segments.append(segment)
        
        # Format the segment for display
        timestamp = f"[{format_time_display(start_time)} → {format_time_display(end_time)}]"
        confidence_indicator = self._get_confidence_indicator(confidence)
        
        formatted_text = f"{timestamp} {confidence_indicator}\n{text}\n\n"
        
        # Add to text edit
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(formatted_text, self._editor_char_format())
        
        # Auto-scroll to bottom
        self.text_edit.ensureCursorVisible()
        
        # Update stats
        self._update_stats()
        
        # Emit signal
        self.transcription_updated.emit(text, start_time, end_time)
    
    def add_sentence(self, text: str, start_time: float, end_time: float,
                     confidence: float = 0.8, language: str = None):
        """
        Add a complete sentence to the transcription panel
        
        Args:
            text: Complete sentence text
            start_time: Start time in seconds
            end_time: End time in seconds
            confidence: Confidence score (0-1)
        """
        print(f"📝 Adding sentence: '{text[:50]}...' ({start_time:.1f}s - {end_time:.1f}s)")
        
        # Create segment
        segment = TranscriptionSegment(
            text=text,
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
            language=language or self._current_language()
        )
        self.segments.append(segment)
        
        # Format with sentence styling
        timestamp = f"[{format_time_display(start_time)} → {format_time_display(end_time)}]"
        confidence_indicator = self._get_confidence_indicator(confidence)
        
        # Add sentence number
        sentence_num = len(self.segments)
        
        formatted_text = f"{timestamp} {confidence_indicator} (Sentence {sentence_num})\n{text}\n\n"
        
        # Add to text edit
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(formatted_text, self._editor_char_format())
        
        # Auto-scroll
        self.text_edit.ensureCursorVisible()
        
        # Update stats
        self._update_stats()
        
        # Emit signal
        self.transcription_updated.emit(text, start_time, end_time)
    
    def test_add_transcription(self):
        """Add a test transcription to verify panel works"""
        self.add_transcription(
            "✅ TEST: This is a test transcription. If you see this text, the transcription panel is working correctly!",
            0.0, 5.0, 0.95
        )
        print("✅ Test transcription added to panel")
    
    def reset_for_new_file(self):
        """Reset panel for new file"""
        self.segments.clear()
        self.srt_entries.clear()
        self.text_edit.clear()
        self._apply_editor_font(self.text_edit.font())
        self._apply_editor_font(self.text_edit.font())
        self.current_line_index = -1
        self._update_stats()
        print("🔄 Transcription panel reset for new file")
    
    def load_srt(self, srt_entries: List[SRTEntry]):
        """
        Load existing SRT entries
        
        Args:
            srt_entries: List of SRTEntry objects
        """
        self.srt_entries = srt_entries
        self.set_mode("srt")
        self._render_srt()
        print(f"📄 Loaded {len(srt_entries)} SRT entries")
    
    def _render_srt(self):
        """Render SRT entries in the text area"""
        self.text_edit.clear()
        self._apply_editor_font(self.text_edit.font())
        
        for entry in self.srt_entries:
            timestamp = f"{seconds_to_srt_time(entry.start_time)} --> {seconds_to_srt_time(entry.end_time)}"
            
            formatted_text = f"{entry.index}\n{timestamp}\n{entry.text}\n\n"
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(formatted_text, self._editor_char_format())
        
        self._update_stats()
    
    def update_position(self, position_seconds: float):
        """
        Update current playback position and highlight corresponding line
        
        Args:
            position_seconds: Current playback position in seconds
        """
        self.current_time = position_seconds
        self.position_label.setText(f"Position: {format_time_display(position_seconds)}")
        
        # Find and highlight current line
        if self.display_mode == "srt" and self.srt_entries:
            self._highlight_current_srt_line(position_seconds)
        elif self.display_mode == "live" and self.segments:
            self._highlight_current_live_line(position_seconds)
    
    def _highlight_current_srt_line(self, position: float):
        """Highlight the SRT line corresponding to current position"""
        for i, entry in enumerate(self.srt_entries):
            if entry.start_time <= position <= entry.end_time:
                if self.current_line_index != i:
                    self.current_line_index = i
                    self._highlight_line_by_index(i)
                return
        
        if self.current_line_index != -1:
            self.current_line_index = -1
            self._clear_highlight()
    
    def _highlight_current_live_line(self, position: float):
        """Highlight the live transcription line corresponding to current position"""
        for i, segment in enumerate(self.segments):
            if segment.start_time <= position <= segment.end_time:
                if self.current_line_index != i:
                    self.current_line_index = i
                    self._highlight_live_line_by_index(i)
                return
        
        if self.current_line_index != -1:
            self.current_line_index = -1
            self._clear_highlight()
    
    def _highlight_live_line_by_index(self, line_index: int):
        """Highlight a specific live line by index"""
        cursor = self.text_edit.textCursor()
        document = self.text_edit.document()
        block = document.begin()
        
        target_block = line_index * 3
        for i in range(target_block):
            if not block.isValid():
                return
            block = block.next()
        
        if block.isValid():
            text_block = block.next()
            if text_block and text_block.isValid():
                cursor.setPosition(text_block.position())
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                
                highlight_format = QTextCharFormat()
                highlight_format.setBackground(QColor(50, 80, 120))
                cursor.mergeCharFormat(highlight_format)
                
                self.text_edit.setTextCursor(cursor)
                self.text_edit.ensureCursorVisible()
    
    def _highlight_line_by_index(self, line_index: int):
        """Highlight a specific SRT line by index"""
        cursor = self.text_edit.textCursor()
        document = self.text_edit.document()
        block = document.begin()
        
        target_block = line_index * 4 + 2
        for i in range(target_block):
            if not block.isValid():
                return
            block = block.next()
        
        if block.isValid():
            cursor.setPosition(block.position())
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            
            highlight_format = QTextCharFormat()
            highlight_format.setBackground(QColor(50, 80, 120))
            cursor.mergeCharFormat(highlight_format)
            
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
    
    def _clear_highlight(self):
        """Clear all highlighting"""
        cursor = self.text_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        
        default_format = QTextCharFormat()
        default_format.setBackground(QColor(30, 30, 35))
        cursor.mergeCharFormat(default_format)
        
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)
    
    def _get_current_srt_entry_index(self) -> int:
        """Get the index of the SRT entry currently being edited"""
        cursor = self.text_edit.textCursor()
        block = cursor.block()
        block_number = block.blockNumber()
        
        # Each SRT entry takes 4 blocks (index, timestamp, text, empty line)
        # So block_number // 4 gives the entry index
        return block_number // 4

    def _current_language(self) -> str:
        """Get the active transcription language from the owning main window."""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'transcriber') and parent.transcriber:
                language = getattr(parent.transcriber, 'language', None)
                if language:
                    return language
            if hasattr(parent, 'current_language') and parent.current_language:
                return parent.current_language
            if hasattr(parent, 'config') and parent.config:
                language = parent.config.get("language", None)
                if language:
                    return language
            parent = parent.parent()
        return "auto"
    
    def edit_current_line(self):
        """Edit the current subtitle line - works for both Live and SRT modes"""
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        block = cursor.block()
        text = block.text()

        # Determine if this is a text line (not timestamp or index)
        is_text_line = False
        original_text = ""
        line_index = -1
        
        if self.display_mode == "srt":
            # In SRT mode, text lines are the 3rd line of each entry
            # Check if this is a text line (not index and not timestamp)
            if text and not text.strip().isdigit() and not "-->" in text:
                is_text_line = True
                original_text = text
                # Get the entry index
                line_index = self._get_current_srt_entry_index()
        else:
            # In Live mode, text lines don't start with [ and don't contain confidence indicators
            if text and not text.strip().startswith('[') and not '🟢' in text and not '🟡' in text and not '🔴' in text:
                is_text_line = True
                original_text = text
                # Get the segment index
                block_number = block.blockNumber()
                line_index = block_number // 3
        
        if is_text_line and original_text:
            dialog = TranscriptionEditDialog(original_text, self._selected_editor_font(), self)
            ok = dialog.exec() == QDialog.DialogCode.Accepted
            new_text = dialog.text()
            
            if ok and new_text != original_text:
                # Update the text in the editor
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.insertText(new_text, self._editor_char_format())
                
                # Get file path and timestamps for training
                file_path = None
                start_time = 0
                end_time = 0
                language = self._current_language()
                
                # Try to get the current audio file path from the parent
                parent = self.parent()
                while parent:
                    if hasattr(parent, 'current_file') and parent.current_file:
                        file_path = parent.current_file.path
                        break
                    parent = parent.parent()
                
                if self.display_mode == "srt" and line_index >= 0 and line_index < len(self.srt_entries):
                    # Update the SRT entry model
                    entry = self.srt_entries[line_index]
                    start_time = entry.start_time
                    end_time = entry.end_time
                    entry.text = new_text
                    print(f"✏️ Updated SRT entry {line_index}: '{original_text}' -> '{new_text}'")
                    
                elif self.display_mode == "live" and line_index >= 0 and line_index < len(self.segments):
                    # Update the segment model
                    segment = self.segments[line_index]
                    start_time = segment.start_time
                    end_time = segment.end_time
                    language = segment.language
                    segment.text = new_text
                    print(f"✏️ Updated segment {line_index}: '{original_text}' -> '{new_text}'")
                
                # Store correction for training
                self._store_correction(
                    original_text, 
                    new_text, 
                    confidence=0.6,
                    start_time=start_time,
                    end_time=end_time,
                    file_path=file_path,
                    language=language
                )
                
                # Update stats
                self._update_stats()
    
    def _store_correction(self, original: str, corrected: str, confidence: float, 
                           start_time: float = 0, end_time: float = 0,
                           file_path: str = None, language: str = None):
        """Store correction for continuous learning with audio timestamps"""
        if self.database_manager and original != corrected:
            
            # Try to get file path if not provided
            if not file_path:
                parent = self.parent()
                while parent:
                    if hasattr(parent, 'current_file') and parent.current_file:
                        file_path = parent.current_file.path
                        break
                    parent = parent.parent()
            
            correction_data = {
                "audio_hash": f"correction_{datetime.now().timestamp()}",
                "original_text": original,
                "corrected_text": corrected,
                "confidence": confidence,
                "language": language or self._current_language(),
                "file_path": file_path or "",
                "start_time": start_time,
                "end_time": end_time
            }
            
            print("Correction stored for training:")
            print(f"   Mode: {self.display_mode}")
            print(f"   File: {file_path}")
            print(f"   Time: {start_time:.1f}s - {end_time:.1f}s")
            print(f"   '{original[:50]}' -> '{corrected[:50]}'")
            
            result = False
            if self.correction_collector:
                result = self.correction_collector.collect_correction(
                    None,
                    original,
                    corrected,
                    confidence,
                    correction_data["language"],
                    file_path,
                    start_time,
                    end_time
                )

            if not result and self.database_manager:
                self.database_manager.add_correction(correction_data)
                result = True
            
            if result:
                print("Correction stored successfully!")
                pending_count = (
                    self.correction_collector.get_pending_count()
                    if self.correction_collector
                    else self.database_manager.get_statistics().get('pending_corrections', 0)
                )
                self.correction_made.emit({
                    **correction_data,
                    "stored": True,
                    "pending_count": pending_count
                })
    
    def find_text(self):
        """Find text in transcription"""
        dialog = FindTextDialog(self._selected_editor_font(), self)
        ok = dialog.exec() == QDialog.DialogCode.Accepted
        text = dialog.text()
        
        if ok and text:
            document = self.text_edit.document()
            cursor = document.find(text)
            
            if not cursor.isNull():
                self.text_edit.setTextCursor(cursor)
                self.text_edit.ensureCursorVisible()
            else:
                QMessageBox.information(self, "Not Found", f"Text '{text}' not found.")
    
    def export_srt(self, file_path: str = None):
        """
        Export transcription as SRT file
        
        Args:
            file_path: Path to save the SRT file (if None, will prompt)
        """
        if isinstance(file_path, bool):
            file_path = None

        print("🔴 EXPORT BUTTON CLICKED - Starting export...")
        print(f"   Display mode: {self.display_mode}")
        print(f"   Segments count: {len(self.segments)}")
        print(f"   SRT entries count: {len(self.srt_entries)}")
        
        if file_path is None:
            from PyQt6.QtWidgets import QFileDialog
            from PyQt6.QtCore import QDir
            from datetime import datetime
            
            default_name = f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
            
            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Export SRT File",
                QDir.homePath() + "/" + default_name,
                "SubRip Subtitle (*.srt);;All Files (*.*)"
            )
            
            print(f"   File dialog returned: {file_path}")
        
        if not file_path:
            print("   User cancelled export")
            return
        
        try:
            if self.display_mode == "srt" and self.srt_entries:
                # Export existing SRT
                print(f"   Exporting existing SRT with {len(self.srt_entries)} entries")
                handler = SRTHandler()
                success = handler.save_file(file_path, self.srt_entries)
                print(f"   Export success: {success}")
                
            elif self.segments:
                # Export from live segments
                print(f"   Exporting from {len(self.segments)} live segments")
                srt_entries = []
                for i, segment in enumerate(self.segments, 1):
                    entry = SRTEntry(
                        index=i,
                        start_time=segment.start_time,
                        end_time=segment.end_time,
                        text=segment.text
                    )
                    srt_entries.append(entry)
                
                handler = SRTHandler()
                success = handler.save_file(file_path, srt_entries)
                print(f"   Export success: {success}")
                
            else:
                print("   No content to export")
                QMessageBox.warning(self, "No Content", "No transcription to export.")
                return
            
            print(f"✅ Export completed: {file_path}")
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"SRT file saved to:\n{file_path}"
            )
            
            self.export_requested.emit(file_path)
            
        except Exception as e:
            print(f"❌ Export error: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Error saving SRT file:\n{str(e)}"
            )
    
    def adjust_sync(self):
        """Adjust timeline offset for all timestamps"""
        offset_ms, ok = QInputDialog.getInt(
            self,
            "Sync Adjustment",
            "Adjust timestamps by (milliseconds):\nPositive = forward, Negative = backward",
            0,
            -5000,
            5000,
            100
        )
        
        if ok and offset_ms != 0:
            offset_seconds = offset_ms / 1000.0
            
            if self.display_mode == "srt" and self.srt_entries:
                for entry in self.srt_entries:
                    entry.start_time = max(0, entry.start_time + offset_seconds)
                    entry.end_time = max(0, entry.end_time + offset_seconds)
                self._render_srt()
                print(f"⏱️ Applied {offset_ms}ms offset to SRT entries")
            elif self.segments:
                for segment in self.segments:
                    segment.start_time = max(0, segment.start_time + offset_seconds)
                    segment.end_time = max(0, segment.end_time + offset_seconds)
                self._render_live()
                print(f"⏱️ Applied {offset_ms}ms offset to {len(self.segments)} segments")
    
    def _render_live(self):
        """Render live segments in text area"""
        self.text_edit.clear()
        
        for segment in self.segments:
            timestamp = f"[{format_time_display(segment.start_time)} → {format_time_display(segment.end_time)}]"
            confidence_indicator = self._get_confidence_indicator(segment.confidence)
            
            formatted_text = f"{timestamp} {confidence_indicator}\n{segment.text}\n\n"
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(formatted_text, self._editor_char_format())
        
        self._update_stats()
    
    def _get_confidence_indicator(self, confidence: float) -> str:
        """Get confidence indicator based on confidence score"""
        if confidence >= 0.8:
            return "🟢"
        elif confidence >= 0.5:
            return "🟡"
        else:
            return "🔴"
    
    def _update_stats(self):
        """Update statistics display"""
        if self.display_mode == "srt":
            segments = len(self.srt_entries)
            words = sum(len(entry.text.split()) for entry in self.srt_entries)
        else:
            segments = len(self.segments)
            words = sum(len(segment.text.split()) for segment in self.segments)
        
        self.stats_label.setText(f"Segments: {segments} | Words: {words}")
    
    def clear_all(self):
        """Clear all transcription data"""
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Are you sure you want to clear all transcription?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.segments.clear()
            self.srt_entries.clear()
            self.text_edit.clear()
            self._apply_editor_font(self.text_edit.font())
            self.current_line_index = -1
            self._update_stats()
            print("🗑️ Cleared all transcription")
    
    def get_text(self) -> str:
        """Get the full text content"""
        return self.text_edit.toPlainText()
    
    def get_segments(self) -> List[TranscriptionSegment]:
        """Get all transcription segments"""
        return self.segments.copy()
    
    def get_srt_entries(self) -> List[SRTEntry]:
        """Get all SRT entries"""
        return self.srt_entries.copy()
    
    def set_font_size(self, size: int):
        """Set font size for the text area"""
        font = self.text_edit.font()
        font.setPointSize(size)
        self._apply_editor_font(font)

    def set_font_family(self, family: str):
        """Set font family for the text area"""
        font = self.text_edit.font()
        font.setFamily(family)
        self._apply_editor_font(font)

    def set_editor_font(self, family: str, size: int):
        """Set editor font and keep toolbar controls in sync."""
        self.font_combo.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.font_combo.setCurrentFont(QFont(family))
        self.font_size_spin.setValue(size)
        self.font_combo.blockSignals(False)
        self.font_size_spin.blockSignals(False)

        self._apply_editor_font(QFont(family, size))

    def _editor_char_format(self) -> QTextCharFormat:
        """Return the active text format for inserted transcription text."""
        char_format = QTextCharFormat()
        char_format.setFont(self._selected_editor_font())
        return char_format

    def _selected_editor_font(self) -> QFont:
        """Return the font selected in the transcription toolbar."""
        font = self.font_combo.currentFont()
        font.setPointSize(self.font_size_spin.value())
        return font

    def _apply_editor_font(self, font: QFont):
        """Apply font to existing and future text in the editor."""
        self.text_edit.document().setDefaultFont(font)
        self.text_edit.setFont(font)
        self.text_edit.setCurrentFont(font)

        char_format = QTextCharFormat()
        char_format.setFont(font)
        self.text_edit.setCurrentCharFormat(char_format)

        cursor = self.text_edit.textCursor()
        previous_position = cursor.position()
        previous_anchor = cursor.anchor()
        cursor.setCharFormat(char_format)

        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeCharFormat(char_format)

        cursor.clearSelection()
        cursor.setPosition(min(previous_anchor, self.text_edit.document().characterCount() - 1))
        if previous_position != previous_anchor:
            cursor.setPosition(
                min(previous_position, self.text_edit.document().characterCount() - 1),
                QTextCursor.MoveMode.KeepAnchor,
            )
        self.text_edit.setTextCursor(cursor)

    def _on_toolbar_font_changed(self):
        """Apply font changes from the toolbar and notify listeners."""
        family = self.font_combo.currentFont().family()
        size = self.font_size_spin.value()
        self._apply_editor_font(QFont(family, size))
        self.font_preferences_changed.emit(family, size)
    
    def set_dark_theme(self, enabled: bool = True):
        """Set dark or light theme"""
        if enabled:
            palette = self.text_edit.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 35))
            palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
            self.text_edit.setPalette(palette)
        else:
            palette = self.text_edit.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
            self.text_edit.setPalette(palette)
    
    def copy_selection(self):
        """Copy selected text to clipboard"""
        self.text_edit.copy()
    
    def select_all(self):
        """Select all text"""
        self.text_edit.selectAll()
    
    def export_as_text(self, file_path: str):
        """Export as plain text (no timestamps)"""
        text = self.text_edit.toPlainText()
        clean_text = re.sub(r'\[.*?\]', '', text)
        clean_text = re.sub(r'[🟢🟡🔴]', '', clean_text)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(clean_text.strip())
        
        print(f"📄 Exported as text to: {file_path}")
    
    def get_current_line_text(self) -> str:
        """Get the text of the current line"""
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText()
