"""
Media workspace controller.

Keeps the media preview, waveform selection, and subtitle editor range state in sync.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal


class MediaWorkspaceController(QObject):
    """Coordinate media-selection state between the player and editor widgets."""

    selection_changed = pyqtSignal(float, float)
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player_widget = None
        self.transcription_panel = None
        self.current_media_path: Optional[str] = None
        self.selection_start: Optional[float] = None
        self.selection_end: Optional[float] = None

    def bind_player_widget(self, player_widget):
        self.player_widget = player_widget
        if hasattr(player_widget, "selection_changed"):
            player_widget.selection_changed.connect(self.set_selection)
        if hasattr(player_widget, "selection_cleared"):
            player_widget.selection_cleared.connect(self.clear_selection)

    def bind_transcription_panel(self, transcription_panel):
        self.transcription_panel = transcription_panel
        self.selection_changed.connect(transcription_panel.set_external_selection_range)
        self.selection_cleared.connect(transcription_panel.clear_external_selection_range)

    def set_media_file(self, file_path: Optional[str]):
        self.current_media_path = file_path
        self.clear_selection()

    def set_selection(self, start: float, end: float):
        start, end = sorted((float(start), float(end)))
        self.selection_start = start
        self.selection_end = end
        self.selection_changed.emit(start, end)

    def clear_selection(self):
        self.selection_start = None
        self.selection_end = None
        self.selection_cleared.emit()

    def mark_selection_start(self, position_seconds: float):
        if self.selection_end is None or position_seconds <= self.selection_end:
            end_value = self.selection_end if self.selection_end is not None else position_seconds + 1.5
            self.set_selection(position_seconds, end_value)
        else:
            self.set_selection(position_seconds, position_seconds + 1.5)

    def mark_selection_end(self, position_seconds: float):
        if self.selection_start is None or position_seconds >= self.selection_start:
            start_value = self.selection_start if self.selection_start is not None else max(0.0, position_seconds - 1.5)
            self.set_selection(start_value, position_seconds)
        else:
            self.set_selection(position_seconds - 1.5, position_seconds)

    def use_current_subtitle_range(self) -> Optional[Tuple[float, float]]:
        if not self.transcription_panel:
            return None

        segment_range = self.transcription_panel.get_selected_segment_range()
        if not segment_range:
            return None

        self.set_selection(*segment_range)
        if self.player_widget and hasattr(self.player_widget, "set_selection"):
            self.player_widget.set_selection(*segment_range)
        return segment_range

    def get_selection_range(self) -> Optional[Tuple[float, float]]:
        if self.selection_start is None or self.selection_end is None:
            return None
        return self.selection_start, self.selection_end
