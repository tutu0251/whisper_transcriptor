"""
Player Widget Module
Media player controls, video display, and waveform visualization
"""

import os
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QFileDialog, QFrame, QApplication,
    QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QPalette, QColor

# Import waveform widget
from src.gui.waveform_widget import WaveformWidget

# Try to import VLC for media playback
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    print("Warning: python-vlc not installed. Media playback will be limited.")


class PlayerWidget(QWidget):
    """Media player widget with controls, signals, and waveform"""
    
    # Signals
    playback_started = pyqtSignal()
    playback_paused = pyqtSignal()
    playback_stopped = pyqtSignal()
    position_changed = pyqtSignal(float)  # Position as float (0-1)
    time_changed = pyqtSignal(int, int)   # Current time ms, total duration ms
    file_loaded = pyqtSignal(str)
    volume_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # VLC instance and player
        self.instance = None
        self.player = None
        self.current_media = None
        self.current_file = None
        self.is_playing = False
        self.duration_ms = 0
        
        # Setup UI
        self.setup_ui()
        self.setup_timer()
        self.init_vlc()
    
    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Video display area
        self.video_frame = QFrame()
        self.video_frame.setMinimumHeight(400)
        self.video_frame.setStyleSheet("""
            QFrame {
                background-color: black;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.video_frame)
        
        # Overlay info label on video frame
        self.info_overlay = QLabel(self.video_frame)
        self.info_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_overlay.setStyleSheet("color: #888; font-size: 14px; background-color: rgba(0,0,0,0.7); padding: 20px;")
        self.info_overlay.setWordWrap(True)
        self.info_overlay.resize(self.video_frame.size())
        self.info_overlay.setText("No media loaded\n\nDrag and drop file or click Open")
        self.info_overlay.show()
        
        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setToolTip("Play/Pause (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(40, 40)
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop)
        controls_layout.addWidget(self.stop_btn)
        
        controls_layout.addSpacing(10)
        
        # Time display
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont("Monospace", 10))
        self.time_label.setMinimumWidth(150)
        controls_layout.addWidget(self.time_label)
        
        controls_layout.addStretch()
        
        # Volume control
        self.volume_label = QLabel("🔊")
        controls_layout.addWidget(self.volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        controls_layout.addWidget(self.volume_slider)
        
        # Speed control
        self.speed_label = QLabel("⚡")
        controls_layout.addWidget(self.speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.setFixedWidth(70)
        self.speed_combo.currentTextChanged.connect(self.set_speed)
        controls_layout.addWidget(self.speed_combo)
        
        layout.addLayout(controls_layout)
        
        # Seek slider
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        layout.addWidget(self.seek_slider)
        
        # Waveform widget
        self.waveform = WaveformWidget()
        self.waveform.waveform_clicked.connect(self.on_waveform_click)
        layout.addWidget(self.waveform)
        
        # File info label
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.file_info_label.setWordWrap(True)
        layout.addWidget(self.file_info_label)
        
        # Accept drag and drop
        self.setAcceptDrops(True)
    
    def setup_timer(self):
        """Setup update timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_position)
        self.update_timer.start(100)  # Update every 100ms
    
    def init_vlc(self):
        """Initialize VLC instance"""
        if VLC_AVAILABLE:
            try:
                self.instance = vlc.Instance("--no-xlib", "--quiet")
                self.player = self.instance.media_player_new()
                
                # Set video output to frame
                if hasattr(self.video_frame, 'winId'):
                    self.player.set_hwnd(int(self.video_frame.winId()))
                
                # Connect events
                self.player.event_manager().event_attach(
                    vlc.EventType.MediaPlayerEndReached, self.on_media_end
                )
                
            except Exception as e:
                print(f"Error initializing VLC: {e}")
                self.player = None
    
    def load_file(self, file_path: str) -> bool:
        """
        Load a media file for playback
        
        Args:
            file_path: Path to media file
            
        Returns:
            True if successful
        """
        if not os.path.exists(file_path):
            return False
        
        self.current_file = file_path
        file_name = Path(file_path).name
        
        # Update file info
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        self.file_info_label.setText(f"{file_name} ({file_size:.1f} MB)")
        
        # Load audio for waveform
        try:
            import librosa
            import numpy as np
            audio, sr = librosa.load(file_path, sr=16000)
            self.waveform.set_audio_data(audio, sr)
            print(f"🎵 Waveform loaded: {len(audio)/sr:.1f} seconds")
        except Exception as e:
            print(f"Error loading waveform: {e}")
            import numpy as np
            self.waveform.set_audio_data(np.array([]), 16000)
        
        if VLC_AVAILABLE and self.player:
            try:
                media = self.instance.media_new(file_path)
                self.player.set_media(media)
                self.current_media = media
                
                # Get duration (might need to wait)
                self.update_timer.singleShot(500, self.update_duration)
                
                # Hide info overlay
                self.info_overlay.hide()
                
                self.file_loaded.emit(file_path)
                print(f"✅ File loaded: {file_name}")
                return True
                
            except Exception as e:
                print(f"Error loading media: {e}")
                self.info_overlay.setText(f"Error loading: {file_name}")
                self.info_overlay.show()
                return False
        else:
            # Fallback: just show file info
            self.info_overlay.setText(f"VLC not available\n\nLoaded: {file_name}\n\nPlayback limited to audio only")
            self.info_overlay.show()
            return True
    
    def update_duration(self):
        """Update media duration"""
        if self.player:
            self.duration_ms = self.player.get_length()
            self.update_time_display()
            print(f"📊 Duration: {self.duration_ms/1000:.1f} seconds")
    
    def play(self):
        """Start playback"""
        if self.player:
            self.player.play()
            self.is_playing = True
            self.play_btn.setText("⏸")
            self.playback_started.emit()
            print("▶ Playback started")
    
    def pause(self):
        """Pause playback"""
        if self.player:
            self.player.pause()
            self.is_playing = False
            self.play_btn.setText("▶")
            self.playback_paused.emit()
            print("⏸ Playback paused")
    
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
            print("⏹ Playback stopped")
    
    def seek_position(self, position: int):
        """
        Seek to position (0-1000)
        
        Args:
            position: Position as integer (0-1000)
        """
        if self.player:
            position_float = position / 1000.0
            self.player.set_position(position_float)
            self.position_changed.emit(position_float)
            time_ms = position_float * self.duration_ms
            self.waveform.set_playback_position(time_ms / 1000)
            print(f"🎯 Seek to position: {position_float:.2f}")
    
    def seek_time(self, time_ms: int):
        """
        Seek to specific time in milliseconds
        
        Args:
            time_ms: Time in milliseconds
        """
        if self.player:
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(time_ms / 1000)
            print(f"🎯 Seek to time: {time_ms/1000:.1f}s")
    
    def on_waveform_click(self, position_seconds: float):
        """
        Seek to position when waveform is clicked
        
        Args:
            position_seconds: Position in seconds
        """
        if self.player:
            time_ms = int(position_seconds * 1000)
            self.player.set_time(time_ms)
            self.waveform.set_playback_position(position_seconds)
            
            if self.duration_ms > 0:
                position_float = time_ms / self.duration_ms
                self.seek_slider.setValue(int(position_float * 1000))
            
            print(f"🎯 Waveform seek: {position_seconds:.2f}s")
    
    def set_volume(self, volume: int):
        """
        Set volume (0-100)
        
        Args:
            volume: Volume level
        """
        if self.player:
            self.player.audio_set_volume(volume)
            self.volume_changed.emit(volume)
    
    def get_volume(self) -> int:
        """Get current volume"""
        if self.player:
            return self.player.audio_get_volume()
        return 70
    
    def set_speed(self, speed_text: str):
        """
        Set playback speed
        
        Args:
            speed_text: Speed string (e.g., "1.0x")
        """
        speed = float(speed_text.replace("x", ""))
        if self.player:
            self.player.set_rate(speed)
            self.speed_changed.emit(speed)
            print(f"⚡ Speed set to: {speed}x")
    
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
            
            # Update seek slider
            if position >= 0:
                self.seek_slider.setValue(int(position * 1000))
            
            # Update time display
            self.update_time_display()
            
            # Update waveform position
            self.waveform.set_playback_position(time_ms / 1000)
            
            # Emit signals
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
        print("🏁 Media ended")
    
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