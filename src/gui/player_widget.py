"""
Player Widget Module
Media player controls, video display, and waveform visualization
"""

import os
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
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
        except Exception as e:
            self.failed.emit(self.file_path, str(e))
        finally:
            self.finished.emit(self.file_path)


class PlayerWidget(QWidget):
    """Media player widget with controls, signals, and waveform"""

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

        self.setup_ui()
        self.setup_timer()
        self.init_vlc()

    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.video_frame = QFrame()
        self.video_frame.setMinimumHeight(400)
        self.video_frame.setStyleSheet(
            """
            QFrame {
                background-color: #111111;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            """
        )
        layout.addWidget(self.video_frame)

        self.info_overlay = QLabel(self.video_frame)
        self.info_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_overlay.setStyleSheet(
            "color: #cccccc; font-size: 14px; "
            "background-color: rgba(30,30,30,0.82); "
            "padding: 20px; border: 1px solid rgba(60,60,60,0.9);"
        )
        self.info_overlay.setWordWrap(True)
        self.info_overlay.resize(self.video_frame.size())
        self.info_overlay.setText("No media loaded\n\nDrag and drop file or click Open")
        self.info_overlay.show()

        control_panel = QFrame()
        control_panel.setStyleSheet(
            """
            QFrame {
                background-color: #181818;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
            """
        )
        control_panel_layout = QVBoxLayout(control_panel)
        control_panel_layout.setContentsMargins(12, 10, 12, 10)
        control_panel_layout.setSpacing(10)
        control_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        control_panel_layout.addWidget(self.seek_slider)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        transport_layout = QHBoxLayout()
        transport_layout.setSpacing(8)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setToolTip("Play/Pause (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        transport_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(40, 40)
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)
        transport_layout.addWidget(self.stop_btn)
        controls_layout.addLayout(transport_layout)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont("Consolas", 10))
        self.time_label.setMinimumWidth(170)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(
            """
            QLabel {
                background-color: #111111;
                border: 1px solid #2d2d30;
                border-radius: 4px;
                padding: 6px 10px;
                color: #d4d4d4;
            }
            """
        )
        controls_layout.addWidget(self.time_label)

        controls_layout.addSpacing(12)

        volume_group = QFrame()
        volume_group.setStyleSheet(
            """
            QFrame {
                background-color: #111111;
                border: 1px solid #2d2d30;
                border-radius: 4px;
            }
            """
        )
        volume_layout = QHBoxLayout(volume_group)
        volume_layout.setContentsMargins(10, 6, 10, 6)
        volume_layout.setSpacing(8)

        self.volume_label = QLabel("🔊")
        self.volume_label.setMinimumWidth(16)
        volume_layout.addWidget(self.volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(volume_group)

        speed_group = QFrame()
        speed_group.setStyleSheet(
            """
            QFrame {
                background-color: #111111;
                border: 1px solid #2d2d30;
                border-radius: 4px;
            }
            """
        )
        speed_layout = QHBoxLayout(speed_group)
        speed_layout.setContentsMargins(10, 6, 10, 6)
        speed_layout.setSpacing(8)

        self.speed_label = QLabel("⚡")
        self.speed_label.setMinimumWidth(16)
        speed_layout.addWidget(self.speed_label)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setFixedWidth(82)
        self.speed_combo.currentTextChanged.connect(self.set_speed)
        speed_layout.addWidget(self.speed_combo)
        controls_layout.addWidget(speed_group)

        control_panel_layout.addLayout(controls_layout)
        layout.addWidget(control_panel)

        self.waveform = WaveformWidget()
        self.waveform.waveform_clicked.connect(self.on_waveform_click)
        layout.addWidget(self.waveform)

        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("color: #9d9d9d; font-size: 10px;")
        self.file_info_label.setWordWrap(True)
        layout.addWidget(self.file_info_label)

        self.setAcceptDrops(True)

    def setup_timer(self):
        """Setup update timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_position)
        self.update_timer.start(100)

    def init_vlc(self):
        """Initialize VLC instance"""
        if VLC_AVAILABLE:
            try:
                self.instance = vlc.Instance("--no-xlib", "--quiet")
                self.player = self.instance.media_player_new()

                if hasattr(self.video_frame, "winId"):
                    self.player.set_hwnd(int(self.video_frame.winId()))

                self.player.event_manager().event_attach(
                    vlc.EventType.MediaPlayerEndReached, self.on_media_end
                )
            except Exception as e:
                print(f"Error initializing VLC: {e}")
                self.player = None

    def load_file(self, file_path: str) -> bool:
        """Load a media file for playback."""
        if not os.path.exists(file_path):
            return False

        self.current_file = file_path
        file_name = Path(file_path).name

        file_size = os.path.getsize(file_path) / (1024 * 1024)
        self.file_info_label.setText(f"{file_name} ({file_size:.1f} MB)")

        self.waveform.set_audio_data(np.array([]), 16000)
        self._start_waveform_loading(file_path)

        if VLC_AVAILABLE and self.player:
            try:
                media = self.instance.media_new(file_path)
                self.player.set_media(media)
                self.current_media = media

                self.update_timer.singleShot(500, self.update_duration)

                self.info_overlay.hide()

                self.file_loaded.emit(file_path)
                print(f"File loaded: {file_name}")
                return True
            except Exception as e:
                print(f"Error loading media: {e}")
                self.info_overlay.setText(f"Error loading: {file_name}")
                self.info_overlay.show()
                return False

        self.info_overlay.setText(
            f"VLC not available\n\nLoaded: {file_name}\n\nPlayback limited to audio only"
        )
        self.info_overlay.show()
        return True

    def _start_waveform_loading(self, file_path: str):
        """Start waveform loading in a background thread."""
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
        """Apply loaded waveform data if it belongs to the current file."""
        if file_path != self.current_file:
            return

        self.failed_waveform_loads.discard(file_path)
        self.waveform.set_audio_data(audio, sample_rate)
        print(f"Waveform loaded: {len(audio) / sample_rate:.1f} seconds")

    def _on_waveform_failed(self, file_path: str, error: str):
        """Handle waveform loading failure without blocking media playback."""
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
        """Update media duration"""
        if self.player:
            self.duration_ms = self.player.get_length()
            self.update_time_display()
            print(f"Duration: {self.duration_ms / 1000:.1f} seconds")

    def play(self):
        """Start playback"""
        if self.player:
            self.player.play()
            self.is_playing = True
            self.play_btn.setText("⏸")
            self.playback_started.emit()
            print("Playback started")

    def pause(self):
        """Pause playback"""
        if self.player:
            self.player.pause()
            self.is_playing = False
            self.play_btn.setText("▶")
            self.playback_paused.emit()
            print("Playback paused")

    def toggle_play(self):
        """Toggle play/pause"""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        """Stop playback"""
        if self.player:
            self.player.stop()
            self.is_playing = False
            self.play_btn.setText("▶")
            self.seek_slider.setValue(0)
            self.time_label.setText("00:00:00 / 00:00:00")
            self.waveform.set_playback_position(0)
            self.playback_stopped.emit()
            print("Playback stopped")

    def seek_position(self, position: int):
        """Seek to position (0-1000)."""
        if self.player:
            position_float = position / 1000.0
            self.player.set_position(position_float)
            self.position_changed.emit(position_float)
            time_ms = position_float * self.duration_ms
            self.waveform.set_playback_position(time_ms / 1000)
            print(f"Seek to position: {position_float:.2f}")

    def seek_time(self, time_ms: int):
        """Seek to specific time in milliseconds."""
        if self.player:
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(time_ms / 1000)
            print(f"Seek to time: {time_ms / 1000:.1f}s")

    def on_waveform_click(self, position_seconds: float):
        """Seek to position when waveform is clicked."""
        if self.player:
            time_ms = int(position_seconds * 1000)
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(position_seconds)

            if self.duration_ms > 0:
                position_float = time_ms / self.duration_ms
                self.seek_slider.setValue(int(position_float * 1000))

            print(f"Waveform seek: {position_seconds:.2f}s")

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        if self.player:
            self.player.audio_set_volume(volume)
            self.volume_changed.emit(volume)

    def get_volume(self) -> int:
        """Get current volume"""
        if self.player:
            return self.player.audio_get_volume()
        return 70

    def set_speed(self, speed_text: str):
        """Set playback speed."""
        speed = float(speed_text.replace("x", ""))
        if self.player:
            self.player.set_rate(speed)
            self.speed_changed.emit(speed)
            print(f"Speed set to: {speed}x")

    def get_speed(self) -> float:
        """Get current playback speed"""
        if self.player:
            return self.player.get_rate()
        return 1.0

    def get_position(self) -> float:
        """Get current playback position (0-1)"""
        if self.player:
            return self.player.get_position()
        return 0.0

    def get_time(self) -> int:
        """Get current time in milliseconds"""
        if self.player:
            return self.player.get_time()
        return 0

    def get_duration(self) -> int:
        """Get media duration in milliseconds"""
        if self.player:
            return self.player.get_length()
        return self.duration_ms

    def update_position(self):
        """Update position display (called by timer)"""
        if self.is_playing and self.player:
            position = self.player.get_position()
            time_ms = self.player.get_time()

            if self.duration_ms == 0:
                self.duration_ms = self.player.get_length()

            if position >= 0:
                self.seek_slider.setValue(int(position * 1000))

            self.update_time_display()
            self.waveform.set_playback_position(time_ms / 1000)

            self.position_changed.emit(position)
            self.time_changed.emit(time_ms, self.duration_ms)

    def update_time_display(self):
        """Update time label"""
        if self.player:
            time_ms = self.player.get_time()
            duration_ms = self.player.get_length()

            time_str = self.format_time(time_ms // 1000)
            duration_str = self.format_time(duration_ms // 1000)
            self.time_label.setText(f"{time_str} / {duration_str}")

    def format_time(self, seconds: int) -> str:
        """Format time as HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def on_media_end(self, event):
        """Handle media end event"""
        self.is_playing = False
        self.play_btn.setText("▶")
        self.waveform.set_playback_position(0)
        self.playback_stopped.emit()
        print("Media ended")

    def resizeEvent(self, event):
        """Handle resize event to update overlay position"""
        super().resizeEvent(event)
        self.info_overlay.resize(self.video_frame.size())
        self.waveform.resize(self.width(), self.waveform.height())

    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.load_file(file_path)
                self.play()

    def get_video_output(self):
        """Get video output widget"""
        return self.video_frame

    def has_video(self) -> bool:
        """Check if current media has video"""
        if self.player:
            media = self.player.get_media()
            if media:
                tracks = media.tracks_info()
                for track in tracks:
                    if track.type == "video":
                        return True
        return False

    def is_seekable(self) -> bool:
        """Check if media is seekable"""
        if self.player:
            return self.player.is_seekable()
        return False

    def get_file_name(self) -> str:
        """Get current file name"""
        if self.current_file:
            return Path(self.current_file).name
        return ""

    def set_waveform_visible(self, visible: bool):
        """Show/hide waveform"""
        self.waveform.setVisible(visible)
