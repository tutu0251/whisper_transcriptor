"""
Player Widget Module
Media preview, transport controls, and waveform/timeline workspace.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.gui.waveform_widget import WaveformWidget

try:
    import vlc

    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("Warning: python-vlc not installed. Media playback will be limited.")


class WaveformLoadWorker(QObject):
    """Load waveform audio data outside the UI thread."""

    progress = pyqtSignal(str, int, str)
    loaded = pyqtSignal(str, object, int)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(self.file_path, 10, "Preparing waveform...")

            import librosa

            self.progress.emit(self.file_path, 35, "Reading audio for waveform...")
            audio, sample_rate = librosa.load(self.file_path, sr=16000)
            self.progress.emit(self.file_path, 90, "Rendering waveform...")
            self.loaded.emit(self.file_path, audio, sample_rate)
        except Exception as exc:
            self.failed.emit(self.file_path, str(exc))
        finally:
            self.finished.emit(self.file_path)


class PlayerWidget(QWidget):
    """Media player widget with transport controls and a selection-aware waveform."""

    playback_started = pyqtSignal()
    playback_paused = pyqtSignal()
    playback_stopped = pyqtSignal()
    position_changed = pyqtSignal(float)
    time_changed = pyqtSignal(int, int)
    file_loaded = pyqtSignal(str)
    volume_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(float)
    waveform_loading_started = pyqtSignal(str)
    waveform_loading_progress = pyqtSignal(str, int, str)
    waveform_loading_finished = pyqtSignal(str)
    waveform_loading_failed = pyqtSignal(str, str)
    selection_changed = pyqtSignal(float, float)
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.instance = None
        self.player = None
        self.current_media = None
        self.current_file = None
        self.waveform_thread = None
        self.waveform_worker = None
        self.failed_waveform_loads = set()
        self.is_playing = False
        self.duration_ms = 0
        self.selection_start = None
        self.selection_end = None

        self.setup_ui()
        self.setup_timer()
        self.init_vlc()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.video_frame = QFrame()
        self.video_frame.setMinimumHeight(330)
        self.video_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111318, stop:1 #1a1f2a);
                border: 1px solid #3a4253;
                border-radius: 8px;
            }
            """
        )
        preview_layout = QVBoxLayout(self.video_frame)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(8)

        self.preview_title = QLabel("Media Preview")
        self.preview_title.setStyleSheet("color: #eef2ff; font-size: 18px; font-weight: 600;")
        preview_layout.addWidget(self.preview_title)

        self.preview_subtitle = QLabel("Review timing, drag waveform ranges, and sync subtitle edits from one pane.")
        self.preview_subtitle.setStyleSheet("color: #95a0b5;")
        self.preview_subtitle.setWordWrap(True)
        preview_layout.addWidget(self.preview_subtitle)

        preview_layout.addStretch()

        self.meta_label = QLabel("No media loaded")
        self.meta_label.setStyleSheet(
            "color: #c6d0e1; background: rgba(20,20,28,0.55); padding: 8px; border-radius: 6px;"
        )
        self.meta_label.setWordWrap(True)
        preview_layout.addWidget(self.meta_label)
        layout.addWidget(self.video_frame, 3)

        self.info_overlay = QLabel(self.video_frame)
        self.info_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_overlay.setStyleSheet(
            "color: #cccccc; font-size: 14px; "
            "background-color: rgba(30,30,30,0.82); "
            "padding: 20px; border: 1px solid rgba(60,60,60,0.9);"
        )
        self.info_overlay.setWordWrap(True)
        self.info_overlay.resize(self.video_frame.size())
        self.info_overlay.setText("No media loaded\n\nDrag and drop a file or open one from the workspace.")
        self.info_overlay.show()

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        self.play_btn = QPushButton("Play")
        self.play_btn.setToolTip("Play")
        self.play_btn.clicked.connect(self.play)
        controls_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Pause")
        self.pause_btn.clicked.connect(self.pause)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)
        controls_layout.addWidget(self.stop_btn)

        self.controller_set_in_btn = QPushButton("Set In")
        self.controller_set_in_btn.clicked.connect(self.mark_selection_start)
        controls_layout.addWidget(self.controller_set_in_btn)

        self.controller_set_out_btn = QPushButton("Set Out")
        self.controller_set_out_btn.clicked.connect(self.mark_selection_end)
        controls_layout.addWidget(self.controller_set_out_btn)

        self.split_here_btn = QPushButton("Split Here")
        self.split_here_btn.setToolTip("Splitting at the playhead is tracked as a pending editor action.")
        controls_layout.addWidget(self.split_here_btn)

        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Speed"))

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.set_speed)
        controls_layout.addWidget(self.speed_combo)
        layout.addLayout(controls_layout)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        layout.addWidget(self.seek_slider)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont("Consolas", 10))
        self.time_label.setVisible(False)

        waveform_box = QGroupBox("Waveform Timeline")
        waveform_layout = QVBoxLayout(waveform_box)
        waveform_layout.setContentsMargins(10, 14, 10, 10)

        self.selection_label = QLabel("Selection: --")
        self.selection_label.setStyleSheet("color: #dce8ff;")
        waveform_layout.addWidget(self.selection_label)

        self.waveform = WaveformWidget()
        self.waveform.waveform_clicked.connect(self.on_waveform_click)
        self.waveform.selection_changed.connect(self.on_waveform_selection_changed)
        self.waveform.selection_cleared.connect(self.on_waveform_selection_cleared)
        waveform_layout.addWidget(self.waveform)

        range_controls = QHBoxLayout()
        self.set_in_btn = QPushButton("Set In")
        self.set_out_btn = QPushButton("Set Out")
        self.clear_range_btn = QPushButton("Clear Range")
        self.use_subtitle_range_btn = QPushButton("Use Subtitle Range")
        for button in (self.set_in_btn, self.set_out_btn, self.clear_range_btn, self.use_subtitle_range_btn):
            range_controls.addWidget(button)
        range_controls.addStretch()
        waveform_layout.addLayout(range_controls)

        range_tip = QLabel("Tip: drag the yellow/red handles or drag inside the selection")
        range_tip.setStyleSheet("color: #95a0b5;")
        range_tip.setWordWrap(True)
        waveform_layout.addWidget(range_tip)
        layout.addWidget(waveform_box, 2)

        self.set_in_btn.clicked.connect(self.mark_selection_start)
        self.set_out_btn.clicked.connect(self.mark_selection_end)
        self.clear_range_btn.clicked.connect(self.clear_selection)

        self.setAcceptDrops(True)

    def setup_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_position)
        self.update_timer.start(100)

    def init_vlc(self):
        if VLC_AVAILABLE:
            try:
                self.instance = vlc.Instance("--no-xlib", "--quiet")
                self.player = self.instance.media_player_new()

                if hasattr(self.video_frame, "winId"):
                    self.player.set_hwnd(int(self.video_frame.winId()))

                self.player.event_manager().event_attach(
                    vlc.EventType.MediaPlayerEndReached, self.on_media_end
                )
            except Exception as exc:
                print(f"Error initializing VLC: {exc}")
                self.player = None

    def load_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False

        self.current_file = file_path
        file_name = Path(file_path).name
        self.clear_selection()
        self.meta_label.setText(f"{file_name}   |   loading waveform...   |   Selection: --")

        self.waveform.set_audio_data(np.array([]), 16000)
        self._start_waveform_loading(file_path)

        if VLC_AVAILABLE and self.player:
            try:
                media = self.instance.media_new(file_path)
                self.player.set_media(media)
                self.current_media = media
                QTimer.singleShot(500, self.update_duration)
                self.info_overlay.hide()
                self.file_loaded.emit(file_path)
                print(f"File loaded: {file_name}")
                return True
            except Exception as exc:
                print(f"Error loading media: {exc}")
                self.info_overlay.setText(f"Error loading: {file_name}")
                self.info_overlay.show()
                return False

        self.info_overlay.setText(
            f"VLC not available\n\nLoaded: {file_name}\n\nPlayback limited to audio-only preview."
        )
        self.info_overlay.show()
        self.file_loaded.emit(file_path)
        return True

    def _start_waveform_loading(self, file_path: str):
        self.waveform_loading_started.emit(file_path)

        thread = QThread(self)
        worker = WaveformLoadWorker(file_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self.waveform_loading_progress)
        worker.loaded.connect(self._on_waveform_loaded)
        worker.failed.connect(self._on_waveform_failed)
        worker.finished.connect(self._on_waveform_thread_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self.waveform_thread = thread
        self.waveform_worker = worker
        thread.start()

    def _on_waveform_loaded(self, file_path: str, audio, sample_rate: int):
        if file_path != self.current_file:
            return

        self.failed_waveform_loads.discard(file_path)
        self.waveform.set_audio_data(audio, sample_rate)
        self._update_meta_label(self.get_time(), self.get_duration())
        print(f"Waveform loaded: {len(audio) / sample_rate:.1f} seconds")

    def _on_waveform_failed(self, file_path: str, error: str):
        if file_path != self.current_file:
            return

        print(f"Error loading waveform: {error}")
        self.failed_waveform_loads.add(file_path)
        self.waveform.set_audio_data(np.array([]), 16000)
        self.waveform_loading_failed.emit(file_path, error)

    def _on_waveform_thread_finished(self, file_path: str):
        if file_path in self.failed_waveform_loads:
            self.failed_waveform_loads.discard(file_path)
            return

        if file_path == self.current_file:
            self.waveform_loading_finished.emit(file_path)

    def update_duration(self):
        if self.player:
            self.duration_ms = self.player.get_length()
            self.update_time_display()
            print(f"Duration: {self.duration_ms / 1000:.1f} seconds")

    def play(self):
        if self.player:
            self.player.play()
            self.is_playing = True
            self.playback_started.emit()
            print("Playback started")

    def pause(self):
        if self.player:
            self.player.pause()
            self.is_playing = False
            self.playback_paused.emit()
            print("Playback paused")

    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        if self.player:
            self.player.stop()
            self.is_playing = False
            self.seek_slider.setValue(0)
            self.time_label.setText("00:00:00 / 00:00:00")
            self.waveform.set_playback_position(0)
            self._update_meta_label(0, self.duration_ms)
            self.playback_stopped.emit()
            print("Playback stopped")

    def seek_position(self, position: int):
        if self.player:
            position_float = position / 1000.0
            self.player.set_position(position_float)
            self.position_changed.emit(position_float)
            time_ms = int(position_float * max(self.duration_ms, 0))
            self.waveform.set_playback_position(time_ms / 1000.0)
            self._update_meta_label(time_ms, self.duration_ms)
            print(f"Seek to position: {position_float:.2f}")

    def seek_time(self, time_ms: int):
        if self.player:
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(time_ms / 1000.0)
            self._update_meta_label(time_ms, self.duration_ms)
            print(f"Seek to time: {time_ms / 1000:.1f}s")

    def on_waveform_click(self, position_seconds: float):
        if self.player:
            time_ms = int(position_seconds * 1000)
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(position_seconds)

            if self.duration_ms > 0:
                position_float = time_ms / self.duration_ms
                self.seek_slider.setValue(int(position_float * 1000))

            self._update_meta_label(time_ms, self.duration_ms)
            print(f"Waveform seek: {position_seconds:.2f}s")

    def on_waveform_selection_changed(self, start: float, end: float):
        self.selection_start = start
        self.selection_end = end
        self.selection_label.setText(
            f"Selection: {self.format_timecode(start)} - {self.format_timecode(end)}"
        )
        self._update_meta_label(self.get_time(), self.get_duration())
        self.selection_changed.emit(start, end)

    def on_waveform_selection_cleared(self):
        self.selection_start = None
        self.selection_end = None
        self.selection_label.setText("Selection: --")
        self._update_meta_label(self.get_time(), self.get_duration())
        self.selection_cleared.emit()

    def mark_selection_start(self):
        current_seconds = self.get_time() / 1000.0
        end_value = self.selection_end if self.selection_end is not None else min(self.waveform.duration, current_seconds + 1.5)
        self.set_selection(current_seconds, end_value)

    def mark_selection_end(self):
        current_seconds = self.get_time() / 1000.0
        start_value = self.selection_start if self.selection_start is not None else max(0.0, current_seconds - 1.5)
        self.set_selection(start_value, current_seconds)

    def set_selection(self, start: float, end: float):
        self.waveform.set_selection(start, end)

    def clear_selection(self):
        self.waveform.clear_selection()

    def get_selection_range(self):
        if self.selection_start is None or self.selection_end is None:
            return None
        return self.selection_start, self.selection_end

    def set_volume(self, volume: int):
        if self.player:
            self.player.audio_set_volume(volume)
            self.volume_changed.emit(volume)

    def get_volume(self) -> int:
        if self.player:
            return self.player.audio_get_volume()
        return 70

    def set_speed(self, speed_text: str):
        speed = float(speed_text.replace("x", ""))
        if self.player:
            self.player.set_rate(speed)
            self.speed_changed.emit(speed)
            print(f"Speed set to: {speed}x")

    def get_speed(self) -> float:
        if self.player:
            return self.player.get_rate()
        return 1.0

    def get_position(self) -> float:
        if self.player:
            return self.player.get_position()
        return 0.0

    def get_time(self) -> int:
        if self.player:
            return self.player.get_time()
        return 0

    def get_duration(self) -> int:
        if self.player:
            return self.player.get_length()
        return self.duration_ms

    def update_position(self):
        if self.is_playing and self.player:
            position = self.player.get_position()
            time_ms = self.player.get_time()

            if self.duration_ms == 0:
                self.duration_ms = self.player.get_length()

            if position >= 0:
                self.seek_slider.setValue(int(position * 1000))

            self.update_time_display()
            self.waveform.set_playback_position(time_ms / 1000.0)
            self.position_changed.emit(position)
            self.time_changed.emit(time_ms, self.duration_ms)

    def update_time_display(self):
        if self.player:
            time_ms = self.player.get_time()
            duration_ms = self.player.get_length()
            time_str = self.format_time(time_ms // 1000)
            duration_str = self.format_time(duration_ms // 1000)
            self.time_label.setText(f"{time_str} / {duration_str}")
            self._update_meta_label(time_ms, duration_ms)

    @staticmethod
    def format_time(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def format_timecode(seconds: float) -> str:
        total_seconds = int(seconds)
        minutes = total_seconds // 60
        secs = total_seconds % 60
        tenths = int(round((seconds - total_seconds) * 10))
        return f"{minutes:02d}:{secs:02d}.{tenths}"

    def on_media_end(self, event):
        self.is_playing = False
        self.waveform.set_playback_position(0)
        self.playback_stopped.emit()
        print("Media ended")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.info_overlay.resize(self.video_frame.size())
        self.waveform.resize(self.width(), self.waveform.height())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.load_file(file_path)
                self.play()

    def get_video_output(self):
        return self.video_frame

    def has_video(self) -> bool:
        if self.player:
            media = self.player.get_media()
            if media:
                tracks = media.tracks_info()
                for track in tracks:
                    if track.type == "video":
                        return True
        return False

    def is_seekable(self) -> bool:
        if self.player:
            return self.player.is_seekable()
        return False

    def get_file_name(self) -> str:
        if self.current_file:
            return Path(self.current_file).name
        return ""

    def set_waveform_visible(self, visible: bool):
        self.waveform.setVisible(visible)

    def _update_meta_label(self, time_ms: int, duration_ms: int):
        file_name = Path(self.current_file).name if self.current_file else "No media loaded"
        current_str = self.format_time(max(0, time_ms) // 1000)
        duration_str = self.format_time(max(0, duration_ms) // 1000) if duration_ms > 0 else "--:--"
        selection_text = (
            f"{self.format_timecode(self.selection_start)} - {self.format_timecode(self.selection_end)}"
            if self.selection_start is not None and self.selection_end is not None
            else "--"
        )
        self.meta_label.setText(f"{file_name}   |   {current_str} / {duration_str}   |   Selection: {selection_text}")
