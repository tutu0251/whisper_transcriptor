"""
Waveform Widget Module
Interactive waveform visualization with draggable range selection.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont


class WaveformWidget(QWidget):
    """Real-time audio waveform display"""
    
    # Signals
    waveform_clicked = pyqtSignal(float)  # Position in seconds when clicked
    selection_changed = pyqtSignal(float, float)
    selection_cleared = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Waveform data
        self.audio_data = None
        self.sample_rate = 16000
        self.duration = 0.0
        self.playback_position = 0.0
        self.is_playing = False

        # Display settings
        self.background_color = QColor("#15171d")
        self.waveform_color = QColor("#0f84e8")
        self.position_color = QColor("#ff6b6b")
        self.grid_color = QColor("#2b3240")
        self.selection_fill_color = QColor(36, 78, 122, 70)
        self.selection_start_color = QColor("#ffd24a")
        self.selection_end_color = QColor("#ff6b6b")
        
        # Zoom level
        self.zoom_level = 1.0
        self.scroll_position = 0
        
        # Selection
        self.selection_start = None
        self.selection_end = None
        self.drag_mode = None
        self.drag_offset = 0.0
        self.handle_threshold_px = 8
        
        self.display_data = np.array([])
        self.setMinimumHeight(170)
        self.setMaximumHeight(210)
        self.setStyleSheet("background-color: #15171d; border: 1px solid #3c3c3c; border-radius: 4px;")
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
    
    def set_audio_data(self, audio_data: np.ndarray, sample_rate: int):
        """
        Set audio data for waveform display
        
        Args:
            audio_data: Audio samples (numpy array)
            sample_rate: Sample rate in Hz
        """
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.duration = len(audio_data) / sample_rate
        
        # Downsample for display (max 5000 points for performance)
        if len(audio_data) > 5000:
            step = len(audio_data) // 5000
            self.display_data = audio_data[::step]
        else:
            self.display_data = audio_data
        
        self.update()
    
    def set_playback_position(self, position_seconds: float):
        """Set current playback position"""
        self.playback_position = position_seconds
        self.update()
    
    def set_selection(self, start: float, end: float):
        """Set selection range in seconds"""
        self.selection_start = min(start, end)
        self.selection_end = max(start, end)
        self.selection_changed.emit(self.selection_start, self.selection_end)
        self.update()
    
    def clear_selection(self):
        """Clear selection"""
        self.selection_start = None
        self.selection_end = None
        self.selection_cleared.emit()
        self.update()
    
    def zoom_in(self):
        """Zoom into waveform"""
        self.zoom_level *= 1.5
        self.update()
    
    def zoom_out(self):
        """Zoom out of waveform"""
        self.zoom_level /= 1.5
        self.update()
    
    def reset_zoom(self):
        """Reset zoom to full view"""
        self.zoom_level = 1.0
        self.scroll_position = 0
        self.update()
    
    def _seconds_to_x(self, seconds: float) -> int:
        """Convert seconds to x coordinate"""
        if self.duration == 0:
            return 0
        
        # Calculate visible range based on zoom
        visible_duration = self.duration / self.zoom_level
        start_time = self.scroll_position * visible_duration
        
        if seconds < start_time:
            return -1
        if seconds > start_time + visible_duration:
            return self.width() + 1
        
        relative_pos = (seconds - start_time) / visible_duration
        return int(relative_pos * self.width())
    
    def _x_to_seconds(self, x: int) -> float:
        """Convert x coordinate to seconds"""
        if self.width() == 0:
            return 0
        
        visible_duration = self.duration / self.zoom_level
        start_time = self.scroll_position * visible_duration
        
        return start_time + (x / self.width()) * visible_duration
    
    def paintEvent(self, event):
        """Paint the waveform"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Draw background
        painter.fillRect(self.rect(), self.background_color)
        
        if self.audio_data is None or len(self.audio_data) == 0:
            # Draw placeholder text
            painter.setPen(QColor(100, 100, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                           "Load audio to see waveform")
            return
        
        # Draw grid
        self._draw_grid(painter)
        
        # Draw waveform
        self._draw_waveform(painter)
        
        # Draw selection overlay
        if self.selection_start is not None and self.selection_end is not None:
            self._draw_selection(painter)
        
        # Draw playback position line
        self._draw_position_line(painter)
        self._draw_selection_label(painter)
    
    def _draw_grid(self, painter: QPainter):
        """Draw time grid"""
        painter.setPen(QPen(self.grid_color, 1))
        
        # Draw vertical lines for time markers
        visible_duration = self.duration / self.zoom_level
        
        # Determine time interval based on zoom level
        if visible_duration <= 10:
            interval = 1  # 1 second
        elif visible_duration <= 60:
            interval = 5  # 5 seconds
        elif visible_duration <= 300:
            interval = 15  # 15 seconds
        else:
            interval = 60  # 1 minute
        
        start_time = self.scroll_position * visible_duration
        first_marker = int(start_time / interval) * interval
        
        for time_marker in np.arange(first_marker, start_time + visible_duration, interval):
            x = self._seconds_to_x(time_marker)
            if 0 <= x <= self.width():
                painter.drawLine(x, 0, x, self.height())
                
                # Draw time label
                minutes = int(time_marker // 60)
                seconds = int(time_marker % 60)
                time_str = f"{minutes:02d}:{seconds:02d}"
                painter.drawText(x + 2, self.height() - 5, time_str)
        
        painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)
    
    def _draw_waveform(self, painter: QPainter):
        """Draw the waveform"""
        if self.display_data is None or len(self.display_data) == 0:
            return
        
        # Calculate visible range
        visible_duration = self.duration / self.zoom_level
        start_time = self.scroll_position * visible_duration
        end_time = start_time + visible_duration
        
        # Get samples in visible range
        start_sample = int(start_time * self.sample_rate)
        end_sample = int(end_time * self.sample_rate)
        
        samples = self.audio_data[max(0, start_sample):min(len(self.audio_data), end_sample)]
        
        if len(samples) == 0:
            return
        
        # Downsample for performance
        max_points = self.width()
        if len(samples) > max_points:
            step = len(samples) // max_points
            samples = samples[::step]
        
        # Calculate waveform points
        center_y = self.height() // 2
        max_amplitude = max(0.1, np.max(np.abs(samples)))
        
        for i, sample in enumerate(samples):
            x = i * (self.width() / max(len(samples), 1))
            amplitude = (sample / max_amplitude) * (center_y - 10)
            
            # Draw line from center to amplitude
            painter.setPen(QPen(self.waveform_color, 1))
            painter.drawLine(int(x), center_y, int(x), int(center_y - amplitude))
            painter.drawLine(int(x), center_y, int(x), int(center_y + amplitude))
    
    def _draw_selection(self, painter: QPainter):
        """Draw selection overlay"""
        start_x = self._seconds_to_x(self.selection_start)
        end_x = self._seconds_to_x(self.selection_end)
        
        if start_x < 0:
            start_x = 0
        if end_x > self.width():
            end_x = self.width()

        if end_x < start_x:
            start_x, end_x = end_x, start_x

        if start_x < end_x:
            selection_rect = QRectF(start_x, 0, max(2, end_x - start_x), self.height())
            painter.fillRect(selection_rect, self.selection_fill_color)
            painter.fillRect(QRectF(start_x, 0, 3, self.height()), self.selection_start_color)
            painter.fillRect(QRectF(end_x, 0, 3, self.height()), self.selection_end_color)
    
    def _draw_position_line(self, painter: QPainter):
        """Draw current playback position line"""
        x = self._seconds_to_x(self.playback_position)
        if 0 <= x <= self.width():
            painter.setPen(QPen(self.position_color, 2))
            painter.drawLine(x, 0, x, self.height())

    def _draw_selection_label(self, painter: QPainter):
        if self.selection_start is None or self.selection_end is None:
            return

        painter.setPen(QColor("#dce8ff"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            10,
            18,
            f"Selection: {self._format_seconds(self.selection_start)} - {self._format_seconds(self.selection_end)}",
        )
    
    def mousePressEvent(self, event):
        """Handle mouse press for seeking or selection dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            seconds = max(0.0, min(self._x_to_seconds(event.pos().x()), self.duration))
            self.waveform_clicked.emit(seconds)

            start_x = self._seconds_to_x(self.selection_start) if self.selection_start is not None else None
            end_x = self._seconds_to_x(self.selection_end) if self.selection_end is not None else None
            x_pos = event.pos().x()

            if start_x is not None and abs(x_pos - start_x) <= self.handle_threshold_px:
                self.drag_mode = "start"
            elif end_x is not None and abs(x_pos - end_x) <= self.handle_threshold_px:
                self.drag_mode = "end"
            elif (
                start_x is not None and end_x is not None and
                min(start_x, end_x) < x_pos < max(start_x, end_x)
            ):
                self.drag_mode = "move"
                self.drag_offset = seconds - min(self.selection_start, self.selection_end)
            else:
                self.selection_start = max(0.0, seconds - 1.5)
                self.selection_end = min(self.duration, seconds + 1.5)
                self.drag_mode = "end"
                self.selection_changed.emit(self.selection_start, self.selection_end)
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for selection."""
        if not self.drag_mode or not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        seconds = max(0.0, min(self._x_to_seconds(event.pos().x()), self.duration))
        if self.drag_mode == "start":
            if self.selection_end is None:
                self.selection_end = seconds
            self.selection_start = min(seconds, self.selection_end - 0.2)
        elif self.drag_mode == "end":
            if self.selection_start is None:
                self.selection_start = seconds
            self.selection_end = max(seconds, self.selection_start + 0.2)
        elif self.drag_mode == "move" and self.selection_start is not None and self.selection_end is not None:
            span = self.selection_end - self.selection_start
            new_start = max(0.0, min(self.duration - span, seconds - self.drag_offset))
            self.selection_start = new_start
            self.selection_end = new_start + span

        self.selection_changed.emit(self.selection_start, self.selection_end)
        self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton and self.drag_mode:
            self.drag_mode = None
            if self.selection_start is not None and self.selection_end is not None:
                if abs(self.selection_end - self.selection_start) < 0.1:
                    self.clear_selection()
                else:
                    self.selection_start = min(self.selection_start, self.selection_end)
                    self.selection_end = max(self.selection_start, self.selection_end)
                    self.selection_changed.emit(self.selection_start, self.selection_end)
            self.update()
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()
    
    def resizeEvent(self, event):
        """Handle resize"""
        super().resizeEvent(event)
        self.update()

    @staticmethod
    def _format_seconds(value: float) -> str:
        minutes = int(value) // 60
        seconds = int(value) % 60
        tenths = int(round((value - int(value)) * 10))
        return f"{minutes:02d}:{seconds:02d}.{tenths}"
