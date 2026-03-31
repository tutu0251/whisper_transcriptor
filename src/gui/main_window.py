"""
Main Window Module
Main application window with menu, status bar, and integrated panels
"""

import os
import sys
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QFileDialog,
    QMessageBox, QStatusBar, QLabel, QApplication,
    QDockWidget, QTabWidget, QPushButton, QSlider,
    QComboBox, QGroupBox, QFormLayout, QCheckBox,
    QSpinBox, QDoubleSpinBox, QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QIcon, QFont, QKeySequence

# Import local modules
from src.core.media_player import MediaPlayer
from src.core.transcriber import Transcriber
from src.core.srt_handler import SRTHandler
from src.core.model_manager import ModelManager
from src.core.audio_extractor import AudioExtractor

from src.gui.player_widget import PlayerWidget
from src.gui.transcription_panel import TranscriptionPanel
from src.gui.srt_editor import SRTEditor
from src.gui.settings_dialog import SettingsDialog
from src.gui.model_manager_dialog import ModelManagerDialog
from src.gui.playlist_widget import PlaylistWidget
from src.gui.status_bar import StatusBar

from src.utils.config import Config
from src.utils.logger import setup_logger, get_logger

# Import learning modules
from src.learning.database_manager import DatabaseManager
from src.learning.correction_collector import CorrectionCollector
from src.learning.background_trainer import BackgroundTrainer

# Import models
from src.models.media_file import MediaFile
from src.models.playback_state import PlaybackState, PlaybackMode, DisplayMode


class MainWindow(QMainWindow):
    """Main application window"""
    
    # Signals
    file_loaded = pyqtSignal(str)
    transcription_started = pyqtSignal()
    transcription_stopped = pyqtSignal()
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        
        # Configuration
        self.config = config
        
        # Core components
        self.media_player: Optional[MediaPlayer] = None
        self.transcriber: Optional[Transcriber] = None
        self.srt_handler = SRTHandler()
        self.model_manager = ModelManager()
        self.audio_extractor = AudioExtractor()
        
        # Learning components
        self.db_manager: Optional[DatabaseManager] = None
        self.correction_collector: Optional[CorrectionCollector] = None
        self.background_trainer: Optional[BackgroundTrainer] = None
        
        # State
        self.current_file: Optional[MediaFile] = None
        self.playback_state = PlaybackState()
        self.current_model = config.get("model_size", "small")
        self.current_language = config.get("language", "auto")
        self.custom_model_path = config.get("custom_model_path", None)
        
        # Setup logging
        self.logger = get_logger()
        
        # Setup UI
        self.setup_window()
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_timers()
        self.setup_learning_system()
        
        # Load settings
        self.load_settings()
        
        self.logger.info("Application initialized")
    
    def setup_window(self):
        """Setup main window properties"""
        self.setWindowTitle("Video/Audio Transcriber")
        self.setMinimumSize(1200, 800)
        
        # Set window icon (if available)
        icon_path = Path(__file__).parent.parent.parent / "resources" / "icons" / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Apply theme
        self.apply_theme()
    
    def setup_ui(self):
        """Setup the main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create main splitter (horizontal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Player and Playlist (as tabs)
        left_tabs = QTabWidget()
        
        # Player tab
        self.player_widget = PlayerWidget()
        left_tabs.addTab(self.player_widget, "🎬 Player")
        
        # Playlist tab
        self.playlist_widget = PlaylistWidget()
        left_tabs.addTab(self.playlist_widget, "📋 Playlist")
        
        main_splitter.addWidget(left_tabs)
        
        # Right panel: Transcription (as tabs)
        right_tabs = QTabWidget()
        
        # Transcription tab
        self.transcription_panel = TranscriptionPanel()
        right_tabs.addTab(self.transcription_panel, "📝 Transcription")
        
        # SRT Editor tab
        self.srt_editor = SRTEditor()
        right_tabs.addTab(self.srt_editor, "✏️ SRT Editor")
        
        main_splitter.addWidget(right_tabs)
        
        # Set splitter sizes (40% left, 60% right)
        main_splitter.setSizes([int(self.width() * 0.4), int(self.width() * 0.6)])
        
        main_layout.addWidget(main_splitter)
        
        # Control bar at bottom
        control_bar = self.create_control_bar()
        main_layout.addWidget(control_bar)
        
        # Connect signals
        self.connect_signals()
    
    def create_control_bar(self) -> QWidget:
        """Create the control bar with playback controls"""
        control_bar = QWidget()
        control_bar.setFixedHeight(80)
        control_bar.setStyleSheet("""
            QWidget {
                background-color: #2d2d30;
                border-top: 1px solid #3e3e42;
            }
        """)
        
        layout = QHBoxLayout(control_bar)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Playback controls group
        playback_group = QHBoxLayout()
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setToolTip("Play/Pause (Space)")
        self.play_btn.clicked.connect(self.toggle_playback)
        playback_group.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedSize(40, 40)
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        playback_group.addWidget(self.stop_btn)
        
        playback_group.addSpacing(20)
        
        # Time display
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setStyleSheet("color: #d4d4d4; font-family: monospace; font-size: 14px;")
        playback_group.addWidget(self.time_label)
        
        layout.addLayout(playback_group)
        
        layout.addSpacing(30)
        
        # Seek slider
        seek_layout = QVBoxLayout()
        seek_layout.setSpacing(2)
        
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.seek_position)
        seek_layout.addWidget(self.seek_slider)
        
        layout.addLayout(seek_layout, 1)
        
        layout.addSpacing(20)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("🔊"))
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        volume_layout.addWidget(self.volume_slider)
        
        layout.addLayout(volume_layout)
        
        layout.addSpacing(20)
        
        # Speed control
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("⚡"))
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        self.speed_combo.setFixedWidth(70)
        speed_layout.addWidget(self.speed_combo)
        
        layout.addLayout(speed_layout)
        
        return control_bar
    
    def setup_menu(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open File...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        export_srt_action = QAction("&Export SRT...", self)
        export_srt_action.setShortcut(QKeySequence.StandardKey.Save)
        export_srt_action.triggered.connect(self.export_srt)
        file_menu.addAction(export_srt_action)
        
        export_text_action = QAction("Export as &Text...", self)
        export_text_action.triggered.connect(self.export_text)
        file_menu.addAction(export_text_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        edit_line_action = QAction("&Edit Current Line", self)
        edit_line_action.setShortcut("Ctrl+E")
        edit_line_action.triggered.connect(self.transcription_panel.edit_current_line)
        edit_menu.addAction(edit_line_action)
        
        find_action = QAction("&Find...", self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(self.transcription_panel.find_text)
        edit_menu.addAction(find_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction("&Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.transcription_panel.copy_selection)
        edit_menu.addAction(copy_action)
        
        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.transcription_panel.select_all)
        edit_menu.addAction(select_all_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self.show_waveform_action = QAction("&Show Waveform", self)
        self.show_waveform_action.setCheckable(True)
        self.show_waveform_action.setChecked(True)
        self.show_waveform_action.triggered.connect(self.toggle_waveform)
        view_menu.addAction(self.show_waveform_action)
        
        view_menu.addSeparator()
        
        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        view_menu.addSeparator()
        
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Transcription menu
        trans_menu = menubar.addMenu("&Transcription")
        
        start_action = QAction("&Start Transcription", self)
        start_action.setShortcut("Ctrl+T")
        start_action.triggered.connect(self.start_transcription)
        trans_menu.addAction(start_action)
        
        stop_action = QAction("S&top Transcription", self)
        stop_action.setShortcut("Ctrl+Shift+T")
        stop_action.triggered.connect(self.stop_transcription)
        trans_menu.addAction(stop_action)
        
        trans_menu.addSeparator()
        
        language_menu = trans_menu.addMenu("&Language")
        self.language_action_group = []
        
        languages = ["auto", "en", "es", "fr", "de", "zh", "ja", "ko", "ru", "ar"]
        for lang in languages:
            action = QAction(lang.upper() if lang == "auto" else lang, self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, l=lang: self.change_language(l))
            language_menu.addAction(action)
            self.language_action_group.append(action)
        
        # Models menu
        models_menu = menubar.addMenu("&Models")
        
        self.model_actions = {}
        for model in ["tiny", "base", "small", "medium", "large"]:
            size_mb = self.model_manager.get_model_size_mb(model)
            action = QAction(f"{model.title()} ({size_mb:.0f} MB)", self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, m=model: self.change_model(m))
            models_menu.addAction(action)
            self.model_actions[model] = action
        
        models_menu.addSeparator()
        
        load_custom_action = QAction("📁 Load Custom Model...", self)
        load_custom_action.triggered.connect(self.load_custom_model_dialog)
        models_menu.addAction(load_custom_action)
        
        model_manager_action = QAction("&Model Manager...", self)
        model_manager_action.triggered.connect(self.open_model_manager)
        models_menu.addAction(model_manager_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        preferences_action = QAction("&Preferences...", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.open_settings)
        settings_menu.addAction(preferences_action)
        
        settings_menu.addSeparator()
        
        theme_menu = settings_menu.addMenu("&Theme")
        
        dark_theme_action = QAction("&Dark", self)
        dark_theme_action.triggered.connect(lambda: self.apply_theme("dark"))
        theme_menu.addAction(dark_theme_action)
        
        light_theme_action = QAction("&Light", self)
        light_theme_action.triggered.connect(lambda: self.apply_theme("light"))
        theme_menu.addAction(light_theme_action)
        
        # Training menu
        train_menu = menubar.addMenu("&Training")
        
        train_now_action = QAction("&Train Now", self)
        train_now_action.triggered.connect(self.train_now)
        train_menu.addAction(train_now_action)
        
        view_stats_action = QAction("&View Training Stats", self)
        view_stats_action.triggered.connect(self.view_training_stats)
        train_menu.addAction(view_stats_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        
        documentation_action = QAction("&Documentation", self)
        documentation_action.triggered.connect(self.open_documentation)
        help_menu.addAction(documentation_action)
    
    def setup_toolbar(self):
        """Setup the main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Open file
        open_action = QAction("📂 Open", self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)
        
        toolbar.addSeparator()
        
        # Playback controls
        play_action = QAction("▶ Play", self)
        play_action.triggered.connect(self.toggle_playback)
        toolbar.addAction(play_action)
        
        stop_action = QAction("■ Stop", self)
        stop_action.triggered.connect(self.stop_playback)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        # Export
        export_action = QAction("💾 Export SRT", self)
        export_action.triggered.connect(self.export_srt)
        toolbar.addAction(export_action)
        
        toolbar.addSeparator()
        
        # Settings
        settings_action = QAction("⚙️ Settings", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)
    
    def setup_statusbar(self):
        """Setup the status bar"""
        self.status_bar = StatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add persistent widgets
        self.model_status = QLabel("Model: not loaded")
        self.status_bar.addPermanentWidget(self.model_status)
        
        self.language_status = QLabel("Lang: auto")
        self.status_bar.addPermanentWidget(self.language_status)
        
        self.correction_status = QLabel("📝 0 corrections")
        self.status_bar.addPermanentWidget(self.correction_status)
    
    def setup_timers(self):
        """Setup timers for UI updates"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_playback_position)
        self.update_timer.start(100)  # Update every 100ms
        
        self.correction_timer = QTimer()
        self.correction_timer.timeout.connect(self.update_correction_status)
        self.correction_timer.start(5000)  # Update every 5 seconds
    
    def setup_learning_system(self):
        """Setup continuous learning components"""
        try:
            # Initialize database
            self.db_manager = DatabaseManager()
            
            # Initialize correction collector
            self.correction_collector = CorrectionCollector(self.db_manager)
            
            # Initialize background trainer
            if self.transcriber:
                self.background_trainer = BackgroundTrainer(self.db_manager, self.transcriber)
                self.background_trainer.start()
            
            # Connect signals
            if self.transcription_panel:
                self.transcription_panel.set_correction_collector(self.correction_collector)
                self.transcription_panel.set_database_manager(self.db_manager)
                self.transcription_panel.correction_made.connect(self.on_correction_made)
            
            self.logger.info("Continuous learning system initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize learning system: {e}")
    
    def connect_signals(self):
        """Connect signals between components"""
        # Player signals
        if hasattr(self.player_widget, 'playback_started'):
            self.player_widget.playback_started.connect(self.on_playback_started)
        if hasattr(self.player_widget, 'playback_stopped'):
            self.player_widget.playback_stopped.connect(self.on_playback_stopped)
        
        # Transcription panel signals
        if hasattr(self.transcription_panel, 'seek_requested'):
            self.transcription_panel.seek_requested.connect(self.seek_position)
        if hasattr(self.transcription_panel, 'export_requested'):
            self.transcription_panel.export_requested.connect(self.on_export_complete)
        
        # Playlist signals
        if hasattr(self.playlist_widget, 'file_selected'):
            self.playlist_widget.file_selected.connect(self.load_file)
    
    def load_settings(self):
        """Load saved settings"""
        # Load language
        language = self.config.get("language", "auto")
        self.change_language(language)
        
        # Load model
        model = self.config.get("model_size", "small")
        self.change_model(model)
        
        # Load custom model if specified
        custom_model = self.config.get("custom_model_path", None)
        if custom_model and Path(custom_model).exists():
            self.load_custom_model(custom_model)
        
        # Load theme
        theme = self.config.get("theme", "dark")
        self.apply_theme(theme)
        
        # Load waveform visibility
        show_waveform = self.config.get("show_waveform", True)
        self.show_waveform_action.setChecked(show_waveform)
        self.toggle_waveform(show_waveform)
        
        # Load last directory
        last_dir = self.config.get("last_directory", "")
        if last_dir and os.path.exists(last_dir):
            pass
    
    def apply_theme(self, theme: str = None):
        """Apply dark or light theme"""
        if theme is None:
            theme = self.config.get("theme", "dark")
        
        theme_path = Path(__file__).parent.parent.parent / "resources" / "styles" / f"{theme}_theme.qss"
        
        if theme_path.exists():
            with open(theme_path, 'r') as f:
                self.setStyleSheet(f.read())
        else:
            # Default dark theme fallback
            self.setStyleSheet("""
                QMainWindow { background-color: #1e1e1e; }
                QLabel { color: #d4d4d4; }
            """)
        
        self.config.set("theme", theme)
    
    def open_file(self):
        """Open a media file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Media File",
            self.config.get("last_directory", ""),
            "Media Files (*.mp4 *.avi *.mkv *.mov *.mp3 *.wav *.flac *.m4a);;All Files (*.*)"
        )
        
        if file_path:
            self.load_file(file_path)
    
    def open_folder(self):
        """Open a folder for batch processing"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            self.config.get("last_directory", "")
        )
        
        if folder_path:
            from src.utils.file_utils import get_media_files
            media_files = get_media_files(folder_path)
            
            for file_path in media_files:
                self.playlist_widget.add_file(file_path)
            
            self.status_bar.set_status(f"Added {len(media_files)} files to playlist")
    
    def load_file(self, file_path: str):
        """Load and play a media file"""
        try:
            # Save to config
            self.config.set("last_directory", str(Path(file_path).parent))
            
            # Load in player
            self.player_widget.load_file(file_path)
            
            # Create media file object
            self.current_file = MediaFile(
                path=file_path,
                duration=self.player_widget.get_duration() / 1000 if hasattr(self.player_widget, 'get_duration') else 0,
                format=Path(file_path).suffix[1:].upper()
            )
            
            # Check for existing SRT
            srt_path = Path(file_path).with_suffix(".srt")
            if srt_path.exists():
                srt_entries = self.srt_handler.load_file(str(srt_path))
                self.transcription_panel.load_srt(srt_entries)
                self.status_bar.set_status(f"Loaded SRT: {srt_path.name}")
            else:
                self.transcription_panel.set_mode("live")
                self.status_bar.set_status(f"Loaded: {Path(file_path).name}")
            
            # Update UI
            self.setWindowTitle(f"Video/Audio Transcriber - {Path(file_path).name}")
            self.file_loaded.emit(file_path)
            
            self.logger.info(f"Loaded file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
    
    def load_custom_model_dialog(self):
        """Open dialog to load custom model"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Custom Model Folder",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder_path:
            self.load_custom_model(folder_path)
    
    def load_custom_model(self, model_path: str):
        """Load a custom Hugging Face model"""
        print(f"🔍 Loading custom model from: {model_path}")
        
        # Check if folder exists
        if not os.path.exists(model_path):
            print(f"❌ Model folder does not exist: {model_path}")
            return
        
        # Check required files
        required_files = ["config.json", "tokenizer_config.json"]
        for f in required_files:
            file_path = Path(model_path) / f
            if not file_path.exists():
                print(f"❌ Missing required file: {f}")
                return
            else:
                print(f"✅ Found: {f}")
        """Load a custom Hugging Face model"""
        self.status_bar.set_status(f"Loading custom model from {model_path}...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            device = self.config.get("device", "auto")
            compute_type = self.config.get("compute_type", "float32")
            language = self.config.get("language", "auto")
            
            self.transcriber = Transcriber(
                model_size="custom",
                device=device,
                compute_type=compute_type,
                language=language,
                custom_model_path=model_path
            )
            
            if self.transcriber.load_model():
                self.status_bar.set_status(f"Custom model loaded from {Path(model_path).name}")
                self.model_status.setText(f"Model: custom")
                self.config.set("custom_model_path", model_path)
                
                # Update background trainer
                if self.background_trainer:
                    self.background_trainer.trainer = self.transcriber
            else:
                self.status_bar.set_status(f"Failed to load custom model")
                
        except Exception as e:
            self.logger.error(f"Failed to load custom model: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load custom model:\n{str(e)}")
        
        QApplication.restoreOverrideCursor()
    
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            self.player_widget.pause()
            self.playback_state.mode = PlaybackMode.PAUSED
            self.play_btn.setText("▶")
        else:
            self.player_widget.play()
            self.playback_state.mode = PlaybackMode.PLAYING
            self.play_btn.setText("⏸")
            
            # Start transcription if in live mode and no SRT
            if hasattr(self.transcription_panel, 'display_mode') and \
               self.transcription_panel.display_mode == "live" and \
               not hasattr(self.transcription_panel, 'srt_entries') or not self.transcription_panel.srt_entries:
                self.start_transcription()
    
    def stop_playback(self):
        """Stop playback"""
        self.player_widget.stop()
        self.playback_state.mode = PlaybackMode.STOPPED
        self.play_btn.setText("▶")
        self.stop_transcription()
    
    def seek_position(self, position: float):
        """Seek to position (0-1 or seconds)"""
        if isinstance(position, float) and position <= 1.0:
            self.player_widget.seek_position(int(position * 1000))
        else:
            self.player_widget.seek_time(int(position))
    
    def change_volume(self, volume: int):
        """Change playback volume"""
        self.player_widget.set_volume(volume)
        self.playback_state.volume = volume
    
    def change_speed(self, speed_text: str):
        """Change playback speed"""
        speed = float(speed_text.replace("x", ""))
        self.player_widget.set_speed(speed)
        self.playback_state.speed = speed
    
    def change_language(self, language: str):
        """Change transcription language"""
        self.current_language = language
        if self.transcriber:
            self.transcriber.set_language(language)
        
        self.language_status.setText(f"Lang: {language.upper()}")
        self.config.set("language", language)
        
        # Update menu checkmarks
        for action in self.language_action_group:
            action.setChecked(action.text().lower() == language)
    
    def change_model(self, model_size: str):
        """Change Whisper model"""
        self.current_model = model_size
        
        # Initialize or update transcriber
        self.init_transcriber(model_size)
        
        # Update UI
        self.model_status.setText(f"Model: {model_size}")
        self.config.set("model_size", model_size)
        
        # Update menu checkmarks
        for m, action in self.model_actions.items():
            action.setChecked(m == model_size)
    
    def init_transcriber(self, model_size: str):
        """Initialize the transcriber with selected model"""
        self.status_bar.set_status(f"Loading {model_size} model...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            # Get device directly from config - don't modify it
            device = self.config.get("device", "auto")
            compute_type = self.config.get("compute_type", "float32")
            
            print(f"🔧 Loading transcriber with device: {device}, compute_type: {compute_type}")
            
            self.transcriber = Transcriber(
                model_size=model_size,
                device=device,  # Pass the raw value from config
                compute_type=compute_type,
                language=self.current_language,
                custom_model_path=self.config.get("custom_model_path", None)
            )
            
            if self.transcriber.load_model():
                self.status_bar.set_status(f"Model {model_size} loaded")
                self.model_status.setText(f"Model: {model_size}")
                
                if self.background_trainer:
                    self.background_trainer.trainer = self.transcriber
            else:
                self.status_bar.set_status(f"Failed to load {model_size}")
                
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")
        
        QApplication.restoreOverrideCursor()
    
    def start_transcription(self):
        """Start real-time transcription"""
        if not self.transcriber or not self.transcriber.is_loaded:
            QMessageBox.warning(self, "No Model", "Please load a model first.")
            return
        
        if not self.current_file:
            return
        
        self.transcription_started.emit()
        self.status_bar.set_status("Transcribing...")
    
    def stop_transcription(self):
        """Stop transcription"""
        self.transcription_stopped.emit()
        self.status_bar.set_status("Transcription stopped")
    
    def export_srt(self):
        """Export transcription as SRT"""
        self.transcription_panel.export_srt()
    
    def export_text(self):
        """Export as plain text"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Text",
            "",
            "Text File (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            self.transcription_panel.export_as_text(file_path)
            self.status_bar.set_status(f"Exported to {file_path}")
    
    def on_playback_started(self):
        """Handle playback started"""
        self.playback_state.mode = PlaybackMode.PLAYING
        self.play_btn.setText("⏸")
    
    def on_playback_stopped(self):
        """Handle playback stopped"""
        self.playback_state.mode = PlaybackMode.STOPPED
        self.play_btn.setText("▶")
        self.seek_slider.setValue(0)
    
    def update_playback_position(self):
        """Update playback position display"""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            position = self.player_widget.get_position()
            time_ms = self.player_widget.get_time()
            duration = self.player_widget.get_duration()
            
            if duration > 0:
                # Update seek slider
                self.seek_slider.setValue(int(position * 1000))
                
                # Update time label
                current_str = self.format_time(time_ms // 1000)
                total_str = self.format_time(duration // 1000)
                self.time_label.setText(f"{current_str} / {total_str}")
                
                # Update transcription panel position
                if hasattr(self.transcription_panel, 'update_position'):
                    self.transcription_panel.update_position(time_ms / 1000)
    
    def update_correction_status(self):
        """Update correction counter in status bar"""
        if self.db_manager:
            stats = self.db_manager.get_statistics()
            pending = stats.get('pending_corrections', 0)
            self.correction_status.setText(f"📝 {pending} corrections pending")
    
    def on_correction_made(self, correction_data: dict):
        """Handle user correction made"""
        self.status_bar.set_status("Correction recorded for learning")
        self.update_correction_status()
    
    def train_now(self):
        """Manually trigger training"""
        if self.background_trainer:
            self.background_trainer.train_now()
            self.status_bar.set_status("Training started in background")
    
    def view_training_stats(self):
        """View training statistics"""
        if self.db_manager:
            stats = self.db_manager.get_statistics()
            
            stats_text = f"""
            <h3>Training Statistics</h3>
            <b>Total Corrections:</b> {stats.get('total_corrections', 0)}<br>
            <b>Pending Corrections:</b> {stats.get('pending_corrections', 0)}<br>
            <b>Trained Corrections:</b> {stats.get('trained_corrections', 0)}<br>
            <b>Vocabulary Size:</b> {stats.get('vocabulary_size', 0)}<br>
            <b>Training Sessions:</b> {stats.get('training_sessions', 0)}<br>
            """
            
            QMessageBox.information(self, "Training Statistics", stats_text)
    
    def on_export_complete(self, file_path: str):
        """Handle export complete"""
        self.status_bar.set_status(f"Exported to {file_path}")
    
    def open_model_manager(self):
        """Open model manager dialog"""
        dialog = ModelManagerDialog(self)
        dialog.exec()
        self.refresh_model_status()
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.config, self)
        dialog.exec()
        
        # Apply changes
        self.apply_theme()
        self.change_language(self.config.get("language", "auto"))
    
    def refresh_model_status(self):
        """Refresh model status display"""
        active_model = self.config.get("model_size", "small")
        self.model_status.setText(f"Model: {active_model}")
    
    # ========== VIEW MENU METHODS ==========
    
    def toggle_waveform(self, checked: bool):
        """Toggle waveform visibility"""
        if hasattr(self.player_widget, 'set_waveform_visible'):
            self.player_widget.set_waveform_visible(checked)
            self.config.set("show_waveform", checked)
            self.status_bar.set_status("Waveform " + ("shown" if checked else "hidden"))
    
    def zoom_in(self):
        """Zoom in on waveform"""
        if hasattr(self.player_widget, 'waveform'):
            self.player_widget.waveform.zoom_in()
            self.status_bar.set_status("Zoomed in")
    
    def zoom_out(self):
        """Zoom out on waveform"""
        if hasattr(self.player_widget, 'waveform'):
            self.player_widget.waveform.zoom_out()
            self.status_bar.set_status("Zoomed out")
    
    def reset_zoom(self):
        """Reset waveform zoom"""
        if hasattr(self.player_widget, 'waveform'):
            self.player_widget.waveform.reset_zoom()
            self.status_bar.set_status("Zoom reset")
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            self.status_bar.set_status("Exited fullscreen")
        else:
            self.showFullScreen()
            self.status_bar.set_status("Entered fullscreen")
    
    def format_time(self, seconds: int) -> str:
        """Format time as HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Video/Audio Transcriber",
            f"""
            <h2>Video/Audio Transcriber</h2>
            <p>Version 1.0.0</p>
            <p>A powerful desktop application for transcribing video and audio files using local Whisper models.</p>
            <p><b>Features:</b><br>
            • Real-time transcription with local Whisper models<br>
            • SRT subtitle import/export<br>
            • Continuous learning from user corrections<br>
            • Custom model support (Hugging Face format)<br>
            • Real-time audio waveform visualization<br>
            • 99+ languages support<br>
            • 100% offline, complete privacy</p>
            <p>© 2025 Your Name</p>
            """
        )
    
    def open_documentation(self):
        """Open documentation"""
        QMessageBox.information(self, "Documentation", "Documentation will be available soon.")
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop background trainer
        if self.background_trainer:
            self.background_trainer.stop()
        
        # Save configuration
        self.config.save()
        
        # Clean up temporary files
        self.audio_extractor.cleanup()
        
        self.logger.info("Application shutting down")
        event.accept()