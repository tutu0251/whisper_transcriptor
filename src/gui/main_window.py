"""
Main Window Module
Main application window with menu, status bar, and integrated panels
"""

import os
import sys
import threading
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
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSettings, QUrl
from PyQt6.QtGui import QAction, QIcon, QFont, QKeySequence, QDesktopServices

# Import local modules
try:
    from src.core.media_player import MediaPlayer
except Exception:
    MediaPlayer = None

from src.core.transcriber import Transcriber
from src.core.srt_handler import SRTHandler
from src.core.model_manager import ModelManager

try:
    from src.core.audio_extractor import AudioExtractor
except Exception:
    AudioExtractor = None

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

    DEFAULT_SHORTCUTS = {
        "open_file": "Ctrl+O",
        "export_srt": "Ctrl+S",
        "edit_current_line": "Ctrl+E",
        "find_text": "Ctrl+F",
        "zoom_in": "Ctrl++",
        "zoom_out": "Ctrl+-",
        "reset_zoom": "Ctrl+0",
        "fullscreen": "F11",
        "start_transcription": "Ctrl+T",
        "stop_transcription": "Ctrl+Shift+T",
        "preferences": "Ctrl+,",
    }
    
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
        self.shortcut_actions = {}
        
        # Transcription timing
        self.last_test_time = 0
        self.last_transcribe_time = 0
        self.cached_audio = None
        self.cached_sr = None
        
        # Sentence chunking setting
        self.sentence_chunking_enabled = config.get("sentence_chunking", True)
        
        # Learning system flag
        self.learning_system_initialized = False
        
        # Setup logging
        self.logger = get_logger()
        
        # Setup UI
        self.setup_window()
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_timers()
        
        # Load settings
        self.load_settings()
        
        self.logger.info("Application initialized")
        print("✅ MainWindow initialized")
    
    @property
    def current_file_path(self):
        """Get current file path for corrections"""
        if self.current_file:
            return self.current_file.path
        return None
    
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
        
        # Connect signals
        self.connect_signals()
    
    def create_control_bar(self) -> QWidget:
        """Create the control bar with playback controls"""
        control_bar = QWidget()
        control_bar.setFixedHeight(80)
        control_bar.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-top: 1px solid #3c3c3c;
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
        self.time_label.setStyleSheet("color: #cccccc; font-family: Consolas, 'Courier New', monospace; font-size: 14px;")
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
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        self.shortcut_actions["open_file"] = open_action
        
        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        export_srt_action = QAction("&Export SRT...", self)
        export_srt_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        export_srt_action.triggered.connect(self.export_srt)
        file_menu.addAction(export_srt_action)
        self.shortcut_actions["export_srt"] = export_srt_action
        
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
        edit_line_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        edit_line_action.triggered.connect(self.transcription_panel.edit_current_line)
        edit_menu.addAction(edit_line_action)
        self.shortcut_actions["edit_current_line"] = edit_line_action
        
        find_action = QAction("&Find...", self)
        find_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        find_action.triggered.connect(self.transcription_panel.find_text)
        edit_menu.addAction(find_action)
        self.shortcut_actions["find_text"] = find_action
        
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
        zoom_in_action.triggered.connect(self.zoom_in)
        view_menu.addAction(zoom_in_action)
        self.shortcut_actions["zoom_in"] = zoom_in_action
        
        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        view_menu.addAction(zoom_out_action)
        self.shortcut_actions["zoom_out"] = zoom_out_action
        
        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.triggered.connect(self.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        self.shortcut_actions["reset_zoom"] = reset_zoom_action
        
        view_menu.addSeparator()
        
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        self.shortcut_actions["fullscreen"] = fullscreen_action
        
        # Transcription menu
        trans_menu = menubar.addMenu("&Transcription")
        
        start_action = QAction("&Start Transcription", self)
        start_action.triggered.connect(self.start_transcription)
        trans_menu.addAction(start_action)
        self.shortcut_actions["start_transcription"] = start_action
        
        stop_action = QAction("S&top Transcription", self)
        stop_action.triggered.connect(self.stop_transcription)
        trans_menu.addAction(stop_action)
        self.shortcut_actions["stop_transcription"] = stop_action
        
        trans_menu.addSeparator()
        
        # Sentence chunking toggle
        self.sentence_chunking_action = QAction("&Sentence-Aware Chunking", self)
        self.sentence_chunking_action.setCheckable(True)
        self.sentence_chunking_action.setChecked(self.sentence_chunking_enabled)
        self.sentence_chunking_action.triggered.connect(self.toggle_sentence_chunking)
        trans_menu.addAction(self.sentence_chunking_action)
        
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
            action = QAction(model.title(), self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, m=model: self.change_model(m))
            models_menu.addAction(action)
            self.model_actions[model] = action
        
        models_menu.addSeparator()
        
        download_all_action = QAction("Download All HF Models", self)
        download_all_action.triggered.connect(self.download_all_hf_models)
        models_menu.addAction(download_all_action)
        
        models_menu.addSeparator()
        
        model_manager_action = QAction("&Model Manager...", self)
        model_manager_action.triggered.connect(self.open_model_manager)
        models_menu.addAction(model_manager_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        preferences_action = QAction("&Preferences...", self)
        preferences_action.triggered.connect(self.open_settings)
        settings_menu.addAction(preferences_action)
        self.shortcut_actions["preferences"] = preferences_action
        
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
        
        train_menu.addSeparator()
        
        refresh_stats_action = QAction("&Refresh Stats", self)
        refresh_stats_action.triggered.connect(self.refresh_correction_status)
        train_menu.addAction(refresh_stats_action)
        
        train_menu.addSeparator()
        
        clear_corrections_action = QAction("&Clear All Corrections", self)
        clear_corrections_action.triggered.connect(self.clear_corrections)
        train_menu.addAction(clear_corrections_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        
        documentation_action = QAction("&Documentation", self)
        documentation_action.triggered.connect(self.open_documentation)
        help_menu.addAction(documentation_action)

        self.apply_configured_shortcuts()
    
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
        
        toolbar.addSeparator()
        
        # Train button
        train_action = QAction("🎓 Train Now", self)
        train_action.triggered.connect(self.train_now)
        toolbar.addAction(train_action)
        
        toolbar.addSeparator()
        
        # Refresh button
        refresh_action = QAction("🔄 Refresh", self)
        refresh_action.triggered.connect(self.refresh_correction_status)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # Test button
        test_action = QAction("🧪 Test", self)
        test_action.triggered.connect(self.test_transcription)
        toolbar.addAction(test_action)
    
    def setup_statusbar(self):
        """Setup the status bar"""
        self.status_bar = StatusBar()
        self.setStatusBar(self.status_bar)
        
        self.model_status = self.status_bar.model_label
        
        self.language_status = self.status_bar.language_label
        
        self.correction_status = self.status_bar.correction_label
        
        self.training_status = self.status_bar.training_label

    def update_model_status(self):
        """Update the status bar with the loaded model name or custom model path"""
        if self.transcriber and self.transcriber.is_loaded:
            model_name = self._get_loaded_model_name()
            self.status_bar.set_model(model_name)
        else:
            self.status_bar.set_model("")

    def _get_loaded_model_name(self) -> str:
        """Return the selected model name for status display."""
        if self.current_model == "custom":
            custom_path = (
                getattr(self, "custom_model_path", None)
                or self.config.get("custom_model_path", None)
                or getattr(self.transcriber, "custom_model_path", None)
            )
            return Path(custom_path).name if custom_path else "custom"

        if self.current_model:
            return self._display_model_name(self.current_model)

        if self.transcriber and getattr(self.transcriber, "custom_model_path", None):
            return Path(self.transcriber.custom_model_path).name

        return ""

    def _display_model_name(self, model_name: str) -> str:
        """Return the user-facing Whisper model name for compact status display."""
        if not model_name:
            return ""

        normalized = str(model_name).strip()
        if normalized == "custom":
            custom_path = self.config.get("custom_model_path", None)
            return Path(custom_path).name if custom_path else "custom"
        if normalized.startswith("whisper-"):
            return normalized
        return f"whisper-{normalized}"

    def update_language_status(self):
        """Update the language status label from the current transcriber language"""
        if self.transcriber and getattr(self.transcriber, 'language', None):
            self.status_bar.set_language(self.transcriber.language)
        else:
            self.status_bar.set_language("AUTO")
    
    def setup_timers(self):
        """Setup timers for UI updates"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_playback_position)
        self.update_timer.start(100)
        
        self.correction_timer = QTimer()
        self.correction_timer.timeout.connect(self.update_correction_status)
        self.correction_timer.start(5000)  # Update every 5 seconds
    
    def setup_learning_system(self):
        """Setup continuous learning components"""
        try:
            # Initialize database
            if not self.db_manager:
                self.db_manager = DatabaseManager()
                print("✅ Database manager initialized")
            
            # Initialize correction collector
            if not self.correction_collector:
                self.correction_collector = CorrectionCollector(self.db_manager)
                print("✅ Correction collector initialized")
            
            # Initialize background trainer (only if transcriber exists)
            if self.transcriber and not self.background_trainer:
                self.background_trainer = BackgroundTrainer(self.db_manager, self.transcriber)
                self.background_trainer.start()
                self.update_trainer_parameters()
                print("✅ Background trainer started")
            elif not self.transcriber:
                print("⚠️ Transcriber not ready, background trainer will start later")
            
            # Connect signals
            if self.transcription_panel:
                print("🔗 Connecting correction collector to transcription panel...")
                self.transcription_panel.set_correction_collector(self.correction_collector)
                self.transcription_panel.set_database_manager(self.db_manager)
                self.transcription_panel.correction_made.connect(self.on_correction_made)
                print("✅ Correction collector connected")
            
            self.learning_system_initialized = True
            self.logger.info("Continuous learning system initialized")
            
            # Update status immediately
            self.refresh_correction_status()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize learning system: {e}")
            print(f"❌ Learning system error: {e}")
            import traceback
            traceback.print_exc()
    
    def start_background_trainer(self):
        """Start background trainer after model is loaded"""
        if self.transcriber and self.db_manager and not self.background_trainer:
            self.background_trainer = BackgroundTrainer(self.db_manager, self.transcriber)
            self.background_trainer.start()
            self.update_trainer_parameters()
            print("✅ Background trainer started after model load")
    
    def update_trainer_parameters(self):
        """Update background trainer parameters from config"""
        if self.background_trainer:
            self.background_trainer.learning_rate = self.config.get("learning_rate", 1e-5)
            self.background_trainer.num_epochs = self.config.get("num_epochs", 3)
            self.background_trainer.batch_size = self.config.get("batch_size", 4)
            self.background_trainer.min_corrections_for_training = self.config.get("min_corrections_for_training", 10)
            print("✅ Trainer parameters updated")
    
    def refresh_correction_status(self):
        """Manually refresh correction status display"""
        print("🔄 Refreshing correction status...")
        if self.db_manager:
            stats = self.db_manager.get_statistics()
            pending = stats.get('pending_corrections', 0)
            trained = stats.get('trained_corrections', 0)
            total = stats.get('total_corrections', 0)
            
            self.status_bar.set_corrections(pending, trained)
            
            if pending > 0:
                self.status_bar.set_training(f"{pending} corrections ready")
            else:
                self.status_bar.set_training("idle")
            
            print(f"📊 Stats - Total: {total}, Pending: {pending}, Trained: {trained}")
            return pending
        else:
            print("⚠️ db_manager is None")
        return 0
    
    def download_hf_model(self, model_size: str):
        """Download a Hugging Face model into the local models folder"""
        hf_id = self.model_manager.get_hf_model_id(model_size)
        if not hf_id:
            QMessageBox.warning(self, "Invalid Model", f"Unknown model: {model_size}")
            return

        if self.model_manager.is_hf_model_available(hf_id):
            QMessageBox.information(self, "Already Downloaded", f"Model {model_size} is already available in the models folder.")
            return

        self.status_bar.set_status(f"Downloading HF model {model_size}...")
        QApplication.processEvents()

        if self.model_manager.download_hf_model(model_size):
            self.status_bar.set_status(f"✅ {model_size.title()} downloaded")
            QMessageBox.information(self, "Download Complete", f"Model {model_size} downloaded successfully.")
        else:
            self.status_bar.set_status(f"❌ Failed to download {model_size}")
            QMessageBox.critical(self, "Download Failed", f"Failed to download model {model_size}.")

    def download_all_hf_models(self):
        """Download all standard HF Whisper models into the local models folder"""
        models = ["tiny", "base", "small", "medium", "large"]
        self.status_bar.set_status("Downloading all HF models...")
        QApplication.processEvents()

        failed = []
        for model_size in models:
            if self.model_manager.is_hf_model_available(self.model_manager.get_hf_model_id(model_size)):
                continue
            if not self.model_manager.download_hf_model(model_size):
                failed.append(model_size)

        if failed:
            self.status_bar.set_status(f"❌ Failed to download: {', '.join(failed)}")
            QMessageBox.critical(self, "Download Failed", f"Failed to download the following models: {', '.join(failed)}")
        else:
            self.status_bar.set_status("✅ All HF models downloaded")
            QMessageBox.information(self, "Download Complete", "All HF models were downloaded successfully.")

    def connect_signals(self):
        """Connect signals between components"""
        if hasattr(self.player_widget, 'playback_started'):
            self.player_widget.playback_started.connect(self.on_playback_started)
        if hasattr(self.player_widget, 'playback_stopped'):
            self.player_widget.playback_stopped.connect(self.on_playback_stopped)
        if hasattr(self.player_widget, 'waveform_loading_started'):
            self.player_widget.waveform_loading_started.connect(self.on_waveform_loading_started)
        if hasattr(self.player_widget, 'waveform_loading_progress'):
            self.player_widget.waveform_loading_progress.connect(self.on_waveform_loading_progress)
        if hasattr(self.player_widget, 'waveform_loading_finished'):
            self.player_widget.waveform_loading_finished.connect(self.on_waveform_loading_finished)
        if hasattr(self.player_widget, 'waveform_loading_failed'):
            self.player_widget.waveform_loading_failed.connect(self.on_waveform_loading_failed)
        
        if hasattr(self.transcription_panel, 'seek_requested'):
            self.transcription_panel.seek_requested.connect(self.seek_position)
        if hasattr(self.transcription_panel, 'export_requested'):
            self.transcription_panel.export_requested.connect(self.on_export_complete)
        if hasattr(self.transcription_panel, 'font_preferences_changed'):
            self.transcription_panel.font_preferences_changed.connect(self.on_transcription_font_changed)
        
        if hasattr(self.playlist_widget, 'file_selected'):
            self.playlist_widget.file_selected.connect(self.load_file)

    def on_waveform_loading_started(self, file_path: str):
        """Show waveform loading progress without blocking the UI."""
        self.status_bar.show_progress(True)
        self.status_bar.set_progress(0)
        self.status_bar.set_status(f"Loading waveform: {Path(file_path).name}")

    def on_waveform_loading_progress(self, file_path: str, value: int, message: str):
        """Update waveform loading progress."""
        if self.current_file and self.current_file.path != file_path:
            return

        self.status_bar.set_progress(value)
        self.status_bar.set_status(message)

    def on_waveform_loading_finished(self, file_path: str):
        """Hide waveform progress when loading finishes."""
        if self.current_file and self.current_file.path != file_path:
            return

        self.status_bar.set_progress(100)
        self.status_bar.show_progress(False)
        self.status_bar.set_status(f"Waveform loaded: {Path(file_path).name}")

    def on_waveform_loading_failed(self, file_path: str, error: str):
        """Report waveform loading failure while keeping media loaded."""
        if self.current_file and self.current_file.path != file_path:
            return

        self.status_bar.show_progress(False)
        self.status_bar.set_status(f"Waveform unavailable: {Path(file_path).name}")
    
    def load_settings(self):
        """Load saved settings"""
        language = self.config.get("language", "auto")
        self.change_language(language)
        
        custom_model = self.config.get("custom_model_path", None)
        if custom_model and Path(custom_model).exists():
            self.current_model = "custom"
            self.load_custom_model(custom_model)
        else:
            model = self.config.get("model_size", "small")
            self.change_model(model)
        
        theme = self.config.get("theme", "dark")
        self.apply_theme(theme)
        self.apply_transcription_font_settings()
        self.apply_configured_shortcuts()
        
        show_waveform = self.config.get("show_waveform", True)
        self.show_waveform_action.setChecked(show_waveform)
        self.toggle_waveform(show_waveform)
        
        # Load sentence chunking setting
        self.sentence_chunking_enabled = self.config.get("sentence_chunking", True)
        if hasattr(self, 'sentence_chunking_action'):
            self.sentence_chunking_action.setChecked(self.sentence_chunking_enabled)
        
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
            self.config.set("last_directory", str(Path(file_path).parent))
            self.player_widget.load_file(file_path)
            
            self.current_file = MediaFile(
                path=file_path,
                duration=self.player_widget.get_duration() / 1000 if hasattr(self.player_widget, 'get_duration') else 0,
                format=Path(file_path).suffix[1:].upper()
            )
            
            # Reset all transcription-related state
            self.cached_audio = None
            self.cached_sr = None
            if hasattr(self, 'processed_sentences'):
                delattr(self, 'processed_sentences')
            self.last_transcribe_time = 0
            if hasattr(self.transcription_panel, 'reset_for_new_file'):
                self.transcription_panel.reset_for_new_file()
            
            # Check for existing SRT
            srt_path = Path(file_path).with_suffix(".srt")
            if srt_path.exists():
                srt_entries = self.srt_handler.load_file(str(srt_path))
                self.transcription_panel.load_srt(srt_entries)
                self.status_bar.set_status(f"Loaded SRT: {srt_path.name}")
            else:
                self.transcription_panel.set_mode("live")
                self.status_bar.set_status(f"Loaded: {Path(file_path).name}")
            
            self.setWindowTitle(f"Video/Audio Transcriber - {Path(file_path).name}")
            self.file_loaded.emit(file_path)
            
            self.logger.info(f"Loaded file: {file_path}")
            print(f"✅ File loaded: {file_path}")
            
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
        
        if not os.path.exists(model_path):
            print(f"❌ Model folder does not exist: {model_path}")
            return
        
        required_files = ["config.json", "tokenizer_config.json"]
        for f in required_files:
            file_path = Path(model_path) / f
            if not file_path.exists():
                print(f"❌ Missing required file: {f}")
                return
            else:
                print(f"✅ Found: {f}")
        
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
                self.current_model = "custom"
                self.custom_model_path = model_path
                self.config.set("custom_model_path", model_path)
                self.config.set("model_size", "custom")
                self.update_model_status()
                self.update_language_status()
                for action in self.model_actions.values():
                    action.setChecked(False)
                print("✅ Custom model loaded successfully")
                
                # Initialize learning system if not already done
                if not self.learning_system_initialized:
                    self.setup_learning_system()
                elif not self.background_trainer:
                    self.start_background_trainer()
                else:
                    self.update_trainer_parameters()
                
                # Refresh status
                self.refresh_correction_status()
            else:
                self.status_bar.set_status(f"Failed to load custom model")
                print("❌ Failed to load custom model")
                
        except Exception as e:
            self.logger.error(f"Failed to load custom model: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load custom model:\n{str(e)}")
        
        QApplication.restoreOverrideCursor()
    
    def test_transcription(self):
        """Test transcription panel"""
        print("🧪 Test button clicked")
        if hasattr(self.transcription_panel, 'test_add_transcription'):
            self.transcription_panel.test_add_transcription()
        else:
            self.transcription_panel.add_transcription(
                "✅ TEST: This is a test transcription. The panel is working!",
                0.0, 5.0, 0.95
            )
        self.status_bar.set_status("Test transcription added")
    
    def toggle_sentence_chunking(self, checked: bool):
        """Toggle sentence-aware chunking"""
        self.sentence_chunking_enabled = checked
        self.config.set("sentence_chunking", checked)
        
        if hasattr(self, 'processed_sentences'):
            delattr(self, 'processed_sentences')
        
        self.status_bar.set_status(
            "Sentence chunking " + ("enabled" if checked else "disabled")
        )
        print(f"🔧 Sentence chunking: {'ON' if checked else 'OFF'}")
        
        if self.current_file:
            reply = QMessageBox.question(
                self,
                "Setting Changed",
                "Sentence chunking setting changed. Reload the current file to apply changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.load_file(self.current_file.path)
    
    def toggle_playback(self):
        """Toggle play/pause"""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            self.player_widget.pause()
            self.playback_state.mode = PlaybackMode.PAUSED
            self.play_btn.setText("▶")
            print("⏸ Playback paused")
        else:
            self.player_widget.play()
            self.playback_state.mode = PlaybackMode.PLAYING
            self.play_btn.setText("⏸")
            print("▶ Playback started")
            
            if hasattr(self.transcription_panel, 'display_mode') and \
               self.transcription_panel.display_mode == "live":
                self.start_transcription()
    
    def stop_playback(self):
        """Stop playback"""
        self.player_widget.stop()
        self.playback_state.mode = PlaybackMode.STOPPED
        self.play_btn.setText("▶")
        self.stop_transcription()
        self.last_transcribe_time = 0
    
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
        
        self.status_bar.set_language(language)
        self.config.set("language", language)
        
        for action in self.language_action_group:
            action.setChecked(action.text().lower() == language)
    
    def change_model(self, model_size: str):
        """Change Whisper model"""
        self.current_model = model_size

        if model_size != "custom":
            self.custom_model_path = None
            self.config.set("custom_model_path", None)
            self.status_bar.set_status(f"Checking local HF model for {model_size}...")
            hf_id = self.model_manager.get_hf_model_id(model_size)
            if hf_id and not self.model_manager.is_hf_model_available(hf_id):
                self.status_bar.set_status(f"Downloading HF model {model_size}...")
                QApplication.processEvents()
                if not self.model_manager.download_hf_model(model_size):
                    QMessageBox.critical(
                        self,
                        "Download Failed",
                        f"Failed to download Hugging Face model: {model_size}.\nPlease install huggingface_hub and try again."
                    )
                    return

        self.init_transcriber(model_size)
        self.config.set("model_size", model_size)

        for m, action in self.model_actions.items():
            action.setChecked(m == model_size)
    
    def init_transcriber(self, model_size: str):
        """Initialize the transcriber with selected model"""
        self.status_bar.set_status(f"Loading {model_size} model...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        try:
            device = self.config.get("device", "auto")
            compute_type = self.config.get("compute_type", "float32")
            
            print(f"🔧 Loading transcriber with device: {device}, compute_type: {compute_type}")
            
            self.transcriber = Transcriber(
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                language=self.current_language,
                custom_model_path=self.config.get("custom_model_path", None)
            )
            
            if self.transcriber.load_model():
                self.status_bar.set_status(f"Model {model_size} loaded")
                self.current_model = model_size
                self.update_model_status()
                self.update_language_status()
                print(f"✅ Model {model_size} loaded successfully")
                
                if not self.learning_system_initialized:
                    self.setup_learning_system()
                elif not self.background_trainer:
                    self.start_background_trainer()
                else:
                    self.update_trainer_parameters()
                
                self.refresh_correction_status()
            else:
                self.status_bar.set_status(f"Failed to load {model_size}")
                print(f"❌ Failed to load model {model_size}")
                
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
        
        print(f"🎤 Starting transcription with model: {self.current_model}")
        self.transcription_started.emit()
        self.status_bar.set_status("Transcribing...")
        self.last_transcribe_time = 0
    
    def stop_transcription(self):
        """Stop transcription"""
        self.transcription_stopped.emit()
        self.status_bar.set_status("Transcription stopped")
        print("⏹️ Transcription stopped")
    
    def transcribe_current_chunk(self, current_time: float):
        """Transcribe the audio with optional sentence awareness"""
        if not self.current_file:
            return
        
        try:
            import librosa
            import numpy as np
            
            if self.cached_audio is None:
                print(f"🎵 Loading audio: {self.current_file.path}")
                self.cached_audio, self.cached_sr = librosa.load(self.current_file.path, sr=16000)
                print(f"✅ Audio loaded: {len(self.cached_audio)/self.cached_sr:.1f}s")
            
            if self.sentence_chunking_enabled and hasattr(self.transcriber, 'transcribe_with_sentences'):
                if not hasattr(self, 'processed_sentences'):
                    print("🎤 Processing full audio with sentence detection...")
                    from src.processing.chunk_manager import ChunkManager
                    self.chunk_manager = ChunkManager(
                        chunk_duration=self.config.get("chunk_duration", 3.0),
                        overlap=self.config.get("chunk_overlap", 0.5)
                    )
                    
                    self.processed_sentences = self.chunk_manager.split_audio_with_sentences(
                        self.cached_audio, 
                        self.cached_sr,
                        self.transcriber
                    )
                    print(f"✅ Found {len(self.processed_sentences)} sentences")
                    
                    for sentence in self.processed_sentences:
                        if hasattr(self.transcription_panel, 'add_sentence'):
                            self.transcription_panel.add_sentence(
                                sentence["text"],
                                sentence["start"],
                                sentence["end"],
                                sentence.get("confidence", 0.85)
                            )
                        else:
                            self.transcription_panel.add_transcription(
                                sentence["text"],
                                sentence["start"],
                                sentence["end"],
                                sentence.get("confidence", 0.85)
                            )
                
                self.transcription_panel.update_position(current_time)
                
            else:
                if not hasattr(self, 'last_transcribe_time'):
                    self.last_transcribe_time = 0
                
                if current_time - self.last_transcribe_time >= 3.0:
                    self.last_transcribe_time = current_time
                    self._transcribe_chunk_traditional(current_time)
                    
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
    
    def _transcribe_chunk_traditional(self, current_time: float):
        """Traditional chunk-based transcription"""
        try:
            start_sample = int(max(0, current_time - 1.0) * self.cached_sr)
            end_sample = int(min(len(self.cached_audio), (current_time + 2.0) * self.cached_sr))
            
            if end_sample > start_sample:
                chunk = self.cached_audio[start_sample:end_sample]
                chunk_start = start_sample / self.cached_sr
                chunk_end = end_sample / self.cached_sr
                
                if len(chunk) > self.cached_sr * 0.5:
                    print(f"🎤 Transcribing {chunk_start:.1f}s - {chunk_end:.1f}s...")
                    text = self.transcriber.transcribe_chunk(chunk)
                    
                    if text and text.strip():
                        self.transcription_panel.add_transcription(
                            text,
                            chunk_start,
                            chunk_end,
                            0.85
                        )
                    else:
                        print(f"⚠️ No text detected at {current_time:.1f}s")
                        
        except Exception as e:
            print(f"❌ Traditional transcription error: {e}")
    
    def update_playback_position(self):
        """Update playback position display and process transcription"""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            position = self.player_widget.get_position()
            time_ms = self.player_widget.get_time()
            duration = self.player_widget.get_duration()
            
            if duration > 0:
                self.seek_slider.setValue(int(position * 1000))
                
                current_str = self.format_time(time_ms // 1000)
                total_str = self.format_time(duration // 1000)
                self.time_label.setText(f"{current_str} / {total_str}")
                
                if hasattr(self.transcription_panel, 'update_position'):
                    self.transcription_panel.update_position(time_ms / 1000)
                
                if self.transcriber and self.transcriber.is_loaded:
                    current_time = time_ms / 1000.0
                    self.transcribe_current_chunk(current_time)
    
    def export_srt(self):
        """Export transcription as SRT"""
        if hasattr(self.transcription_panel, 'export_srt'):
            self.transcription_panel.export_srt()
        else:
            QMessageBox.warning(self, "Export Error", "Export function not available")
    
    def export_text(self):
        """Export as plain text"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Text",
            "",
            "Text File (*.txt);;All Files (*.*)"
        )
        
        if file_path and hasattr(self.transcription_panel, 'export_as_text'):
            self.transcription_panel.export_as_text(file_path)
            self.status_bar.set_status(f"Exported to {file_path}")
    
    def on_playback_started(self):
        """Handle playback started"""
        self.playback_state.mode = PlaybackMode.PLAYING
        self.play_btn.setText("⏸")
        print("🎵 Playback started")
    
    def on_playback_stopped(self):
        """Handle playback stopped"""
        self.playback_state.mode = PlaybackMode.STOPPED
        self.play_btn.setText("▶")
        self.seek_slider.setValue(0)
        print("⏹️ Playback stopped")
    
    def update_correction_status(self):
        """Update correction counter in status bar (called by timer)"""
        if self.db_manager:
            stats = self.db_manager.get_statistics()
            pending = stats.get('pending_corrections', 0)
            trained = stats.get('trained_corrections', 0)
            self.status_bar.set_corrections(pending, trained)
            
            if pending > 0:
                self.status_bar.set_training(f"{pending} corrections ready")
            else:
                self.status_bar.set_training("idle")
    
    def on_correction_made(self, correction_data: dict):
        """Handle user correction made"""
        print(f"📝 Correction received: {correction_data.get('original_text', '')[:50]} -> {correction_data.get('corrected_text', '')[:50]}")
        self.status_bar.set_status("Correction recorded for learning")
        
        # Force immediate update
        self.refresh_correction_status()
    
    def train_now(self):
        """Manually trigger training"""
        if not self.background_trainer:
            if self.transcriber and self.db_manager:
                self.start_background_trainer()
            else:
                QMessageBox.warning(self, "No Trainer", 
                    "Background trainer not available.\n\n"
                    "Make sure:\n"
                    "1. A model is loaded\n"
                    "2. Database is initialized\n"
                    "3. You have made some corrections")
                return
        
        if self.db_manager:
            stats = self.db_manager.get_statistics()
            pending = stats.get('pending_corrections', 0)
            if pending == 0:
                QMessageBox.information(self, "No Corrections", 
                    "No corrections to train.\n\n"
                    "Edit some transcriptions first (double-click a line and change text).")
                return
        
        self.status_bar.set_status("Starting training...")
        self.status_bar.set_training("in progress...")
        
        def do_training():
            try:
                self.background_trainer.train_now()
                self.refresh_correction_status()
                self.status_bar.set_status("Training complete")
            except Exception as e:
                print(f"❌ Training error: {e}")
                self.status_bar.set_status(f"Training error: {e}")
                self.status_bar.set_training("failed")
        
        thread = threading.Thread(target=do_training, daemon=True)
        thread.start()
    
    def view_training_stats(self):
        """View training statistics"""
        if not self.db_manager:
            QMessageBox.warning(self, "No Data", "No training data available.")
            return
        
        stats = self.db_manager.get_statistics()
        history = self.db_manager.get_training_history(limit=10)
        vocabulary = self.db_manager.get_vocabulary(min_count=2, limit=30)
        
        stats_text = f"""
        <h3>Training Statistics</h3>
        <table width="100%">
         <tr><td><b>Total Corrections:</b></td><td>{stats.get('total_corrections', 0)}</td></tr>
         <tr><td><b>Pending Corrections:</b></td><td>{stats.get('pending_corrections', 0)}</td></tr>
         <tr><td><b>Trained Corrections:</b></td><td>{stats.get('trained_corrections', 0)}</td></tr>
         <tr><td><b>Vocabulary Size:</b></td><td>{stats.get('vocabulary_size', 0)}</td></tr>
         <tr><td><b>Training Sessions:</b></td><td>{stats.get('training_sessions', 0)}</td></tr>
         <tr><td><b>Completed Trainings:</b></td><td>{stats.get('completed_trainings', 0)}</td></tr>
        </table>
        """
        
        if history:
            stats_text += "<h3>Recent Training Sessions</h3>"
            stats_text += "<table width='100%'><tr><th>Session</th><th>Corrections</th><th>Status</th><th>Date</th></tr>"
            for session in history[:5]:
                date = session.get('start_time', '')[:16] if session.get('start_time') else 'N/A'
                stats_text += f"<tr><td>{session['id']}</td><td>{session.get('corrections_count', 0)}</td><td>{session.get('status', 'unknown')}</td><td>{date}</td></tr>"
            stats_text += "</table>"
        
        if vocabulary:
            stats_text += "<h3>Learned Vocabulary</h3>"
            stats_text += "<div style='max-height: 200px; overflow-y: auto;'>"
            for word in vocabulary[:20]:
                stats_text += f"• <b>{word['word']}</b> ({word['correction_count']} corrections)<br>"
            stats_text += "</div>"
        
        QMessageBox.information(self, "Training Statistics", stats_text)
    
    def clear_corrections(self):
        """Clear all corrections from database"""
        if not self.db_manager:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear All Corrections",
            "Are you sure you want to clear all corrections?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            count = self.db_manager.clear_all_corrections()
            self.refresh_correction_status()
            self.status_bar.set_status(f"Cleared {count} corrections")
            QMessageBox.information(self, "Cleared", f"Cleared {count} corrections from database.")
    
    def on_export_complete(self, file_path: str):
        """Handle export complete"""
        self.status_bar.set_status(f"Exported to {file_path}")
    
    def open_model_manager(self):
        """Open model manager dialog"""
        dialog = ModelManagerDialog(self)
        dialog.model_changed.connect(self.on_model_manager_selection)
        dialog.exec()
        self.refresh_model_status()

    def on_model_manager_selection(self, model_value: str):
        """Apply a model selected from the model manager dialog."""
        model_value = str(model_value).strip()
        if not model_value:
            return

        model_path = Path(model_value)
        if model_path.exists() and model_path.is_dir():
            self.load_custom_model(str(model_path))
            return

        self.change_model(model_value)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.config, self)
        dialog.exec()
        
        self.apply_theme()
        self.change_language(self.config.get("language", "auto"))
        self.apply_transcription_font_settings()
        self.apply_configured_shortcuts()
        
        self.sentence_chunking_enabled = self.config.get("sentence_chunking", True)
        if hasattr(self, 'sentence_chunking_action'):
            self.sentence_chunking_action.setChecked(self.sentence_chunking_enabled)
        
        self.update_trainer_parameters()
        self.refresh_correction_status()
    
    def refresh_model_status(self):
        """Refresh model status display"""
        self.update_model_status()

    def apply_transcription_font_settings(self):
        """Apply configured font settings to the transcription editor."""
        if not self.transcription_panel:
            return

        family = self.config.get("font_family", "Monospace")
        size = self.config.get("font_size", 11)
        if hasattr(self.transcription_panel, "set_editor_font"):
            self.transcription_panel.set_editor_font(family, size)

    def apply_configured_shortcuts(self):
        """Apply configured keyboard shortcuts to registered actions."""
        shortcuts = self.config.get("shortcuts", {})
        for key, action in self.shortcut_actions.items():
            shortcut = shortcuts.get(key, self.DEFAULT_SHORTCUTS.get(key, ""))
            action.setShortcut(QKeySequence(shortcut) if shortcut else QKeySequence())

    def on_transcription_font_changed(self, family: str, size: int):
        """Persist transcription font changes from the toolbar controls."""
        self.config.set("font_family", family)
        self.config.set("font_size", size)
        self.config.save()

    def toggle_playback(self):
        """Toggle play/pause using the player widget controls."""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            self.player_widget.pause()
            self.playback_state.mode = PlaybackMode.PAUSED
            print("Playback paused")
        else:
            self.player_widget.play()
            self.playback_state.mode = PlaybackMode.PLAYING
            print("Playback started")

            if hasattr(self.transcription_panel, "display_mode") and \
               self.transcription_panel.display_mode == "live":
                self.start_transcription()

    def stop_playback(self):
        """Stop playback without relying on removed bottom-bar widgets."""
        self.player_widget.stop()
        self.playback_state.mode = PlaybackMode.STOPPED
        self.stop_transcription()
        self.last_transcribe_time = 0

    def update_playback_position(self):
        """Update playback position and process transcription."""
        if self.playback_state.mode == PlaybackMode.PLAYING:
            time_ms = self.player_widget.get_time()
            duration = self.player_widget.get_duration()

            if duration > 0:
                if hasattr(self.transcription_panel, "update_position"):
                    self.transcription_panel.update_position(time_ms / 1000)

                if self.transcriber and self.transcriber.is_loaded:
                    current_time = time_ms / 1000.0
                    self.transcribe_current_chunk(current_time)

    def on_playback_started(self):
        """Handle playback started."""
        self.playback_state.mode = PlaybackMode.PLAYING
        print("Playback started")

    def on_playback_stopped(self):
        """Handle playback stopped."""
        self.playback_state.mode = PlaybackMode.STOPPED
        print("Playback stopped")
    
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
            • Sentence-aware chunking<br>
            • 99+ languages support<br>
            • 100% offline, complete privacy</p>
            <p>© 2025 Your Name</p>
            """
        )
    
    def open_documentation(self):
        """Open documentation"""
        doc_path = Path(__file__).parent.parent.parent / "docs" / "user-guide.html"
        if not doc_path.exists():
            QMessageBox.warning(
                self,
                "Documentation Missing",
                f"Documentation file not found:\n{doc_path}"
            )
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc_path.resolve())))
        if not opened:
            QMessageBox.warning(
                self,
                "Open Failed",
                f"Could not open documentation:\n{doc_path}"
            )
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.background_trainer:
            self.background_trainer.stop()
        
        self.config.save()
        self.audio_extractor.cleanup()
        
        self.logger.info("Application shutting down")
        event.accept()
