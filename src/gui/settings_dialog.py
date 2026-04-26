"""
Settings Dialog Module
Application preferences dialog with CUDA support and training parameters
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QDialogButtonBox, QGroupBox, QWidget, QLabel,
    QHBoxLayout, QSlider, QLineEdit, QFileDialog,
    QPushButton, QMessageBox, QKeySequenceEdit
)
from PyQt6.QtCore import Qt, pyqtSignal

import torch

# Check CUDA availability
CUDA_AVAILABLE = torch.cuda.is_available()
if CUDA_AVAILABLE:
    GPU_NAME = torch.cuda.get_device_name(0)
    GPU_MEMORY_GB = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"CUDA detected: {GPU_NAME} ({GPU_MEMORY_GB:.1f} GB)")


class SettingsDialog(QDialog):
    """Application settings dialog"""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.shortcut_editors = {}
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # ========== Transcription Tab ==========
        trans_tab = QWidget()
        trans_layout = QVBoxLayout(trans_tab)
        
        # Language group
        lang_group = QGroupBox("Language Settings")
        lang_layout = QFormLayout(lang_group)
        
        self.language_combo = QComboBox()
        languages = ["auto", "en", "es", "fr", "de", "zh", "ja", "ko", "ru", "ar", "pt", "it", "nl", "pl", "tr"]
        self.language_combo.addItems(languages)
        self.language_combo.setToolTip("Select transcription language (auto = auto-detect)")
        lang_layout.addRow("Transcription Language:", self.language_combo)
        
        trans_layout.addWidget(lang_group)
        
        # Chunk settings group
        chunk_group = QGroupBox("Audio Chunking")
        chunk_layout = QFormLayout(chunk_group)
        
        self.chunk_size = QDoubleSpinBox()
        self.chunk_size.setRange(1.0, 5.0)
        self.chunk_size.setSingleStep(0.5)
        self.chunk_size.setSuffix(" seconds")
        self.chunk_size.setToolTip("Duration of each audio chunk for transcription")
        chunk_layout.addRow("Chunk Duration:", self.chunk_size)
        
        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(0.0, 2.0)
        self.overlap.setSingleStep(0.1)
        self.overlap.setSuffix(" seconds")
        self.overlap.setToolTip("Overlap between chunks for smooth transitions")
        chunk_layout.addRow("Chunk Overlap:", self.overlap)
        
        # Sentence chunking toggle
        self.sentence_chunking = QCheckBox("Enable Sentence-Aware Chunking")
        self.sentence_chunking.setToolTip(
            "Automatically detect sentence boundaries and group words into complete sentences.\n"
            "Disable for real-time word-by-word display."
        )
        chunk_layout.addRow("", self.sentence_chunking)
        
        trans_layout.addWidget(chunk_group)
        
        # Whisper parameters group
        whisper_group = QGroupBox("Whisper Parameters")
        whisper_layout = QFormLayout(whisper_group)
        
        self.beam_size = QSpinBox()
        self.beam_size.setRange(1, 10)
        self.beam_size.setValue(5)
        self.beam_size.setToolTip("Higher beam size = more accurate but slower")
        whisper_layout.addRow("Beam Size:", self.beam_size)
        
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 1.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(0.0)
        self.temperature.setToolTip("Temperature for sampling (0 = deterministic)")
        whisper_layout.addRow("Temperature:", self.temperature)
        
        trans_layout.addWidget(whisper_group)
        trans_layout.addStretch()
        
        tabs.addTab(trans_tab, "Transcription")
        
        # ========== Performance Tab ==========
        perf_tab = QWidget()
        perf_layout = QVBoxLayout(perf_tab)
        
        # Hardware group
        hardware_group = QGroupBox("Hardware Settings")
        hardware_layout = QFormLayout(hardware_group)
        
        # Device selection
        self.device_combo = QComboBox()
        if CUDA_AVAILABLE:
            self.device_combo.addItem("auto", "auto")
            self.device_combo.addItem("cpu", "cpu")
            self.device_combo.addItem(f"cuda ({GPU_NAME})", "cuda")
        else:
            self.device_combo.addItem("auto", "auto")
            self.device_combo.addItem("cpu", "cpu")
        hardware_layout.addRow("Compute Device:", self.device_combo)
        
        # Compute type options
        self.precision_combo = QComboBox()
        if CUDA_AVAILABLE:
            self.precision_combo.addItems(["float32", "float16", "int8"])
            self.precision_combo.setCurrentText("float32")
            self.precision_combo.setToolTip(
                "float32: Most stable (recommended)\n"
                "float16: Faster but may cause issues\n"
                "int8: Fastest but lower accuracy"
            )
        else:
            self.precision_combo.addItems(["int8", "float32"])
            self.precision_combo.setCurrentText("int8")
            self.precision_combo.setToolTip("int8: Faster on CPU, float32: More accurate")
        hardware_layout.addRow("Compute Type:", self.precision_combo)
        
        # GPU memory info
        if CUDA_AVAILABLE:
            gpu_info_label = QLabel(f"{GPU_NAME} ({GPU_MEMORY_GB:.1f} GB)")
            gpu_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            hardware_layout.addRow("GPU:", gpu_info_label)
            
            self.gpu_memory_label = QLabel("Checking...")
            hardware_layout.addRow("GPU Memory Usage:", self.gpu_memory_label)
            
            self.clear_cache_btn = QPushButton("Clear GPU Cache")
            self.clear_cache_btn.clicked.connect(self.clear_gpu_cache)
            hardware_layout.addRow("", self.clear_cache_btn)
        
        # CPU threads
        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 16)
        self.thread_count.setValue(4)
        self.thread_count.setToolTip("Number of CPU threads for processing")
        hardware_layout.addRow("CPU Threads:", self.thread_count)
        
        perf_layout.addWidget(hardware_group)
        
        # Model cache group
        cache_group = QGroupBox("Model Cache")
        cache_layout = QFormLayout(cache_group)
        
        self.cache_path = QLineEdit()
        self.cache_path.setReadOnly(True)
        cache_path_layout = QHBoxLayout()
        cache_path_layout.addWidget(self.cache_path)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_cache_path)
        cache_path_layout.addWidget(browse_btn)
        
        cache_layout.addRow("Cache Location:", cache_path_layout)
        
        self.cache_size_label = QLabel("Calculating...")
        cache_layout.addRow("Cache Size:", self.cache_size_label)
        
        perf_layout.addWidget(cache_group)
        perf_layout.addStretch()
        
        tabs.addTab(perf_tab, "Performance")
        
        # ========== Appearance Tab ==========
        appear_tab = QWidget()
        appear_layout = QVBoxLayout(appear_tab)
        
        # Theme group
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        theme_layout.addRow("Theme:", self.theme_combo)
        
        appear_layout.addWidget(theme_group)
        
        # Font group
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family = QComboBox()
        self.font_family.addItems(["Monospace", "Consolas", "Courier New", "Arial", "Segoe UI"])
        font_layout.addRow("Font Family:", self.font_family)
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.font_size.setValue(11)
        font_layout.addRow("Font Size:", self.font_size)
        
        appear_layout.addWidget(font_group)
        
        # Layout group
        layout_group = QGroupBox("Layout")
        layout_layout = QFormLayout(layout_group)
        
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Horizontal (Video left, Text right)", "Vertical (Video top, Text bottom)"])
        layout_layout.addRow("Layout:", self.layout_combo)
        
        appear_layout.addWidget(layout_group)
        appear_layout.addStretch()
        
        tabs.addTab(appear_tab, "Appearance")

        # ========== Shortcuts Tab ==========
        shortcuts_tab = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_tab)

        shortcuts_group = QGroupBox("Keyboard Shortcuts")
        shortcuts_form = QFormLayout(shortcuts_group)

        shortcut_rows = [
            ("open_file", "Open File"),
            ("export_srt", "Export SRT"),
            ("edit_current_line", "Edit Current Line"),
            ("find_text", "Find"),
            ("start_transcription", "Start Transcription"),
            ("stop_transcription", "Stop Transcription"),
            ("zoom_in", "Zoom In"),
            ("zoom_out", "Zoom Out"),
            ("reset_zoom", "Reset Zoom"),
            ("fullscreen", "Fullscreen"),
            ("preferences", "Preferences"),
        ]

        for key, label in shortcut_rows:
            editor = QKeySequenceEdit()
            editor.setClearButtonEnabled(True)
            self.shortcut_editors[key] = editor
            shortcuts_form.addRow(f"{label}:", editor)

        shortcuts_layout.addWidget(shortcuts_group)
        shortcuts_layout.addWidget(
            QLabel("Click a field and press a new key combination. Leave it empty to disable that shortcut.")
        )
        shortcuts_layout.addStretch()

        tabs.addTab(shortcuts_tab, "Shortcuts")
        
        # ========== Export Tab ==========
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        
        # Format group
        format_group = QGroupBox("Export Format")
        format_layout = QFormLayout(format_group)
        
        self.export_format = QComboBox()
        self.export_format.addItems(["SRT (.srt)", "WebVTT (.vtt)", "Plain Text (.txt)", "JSON (.json)"])
        format_layout.addRow("Default Format:", self.export_format)
        
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["utf-8", "utf-16", "ascii"])
        format_layout.addRow("Encoding:", self.encoding_combo)
        
        export_layout.addWidget(format_group)
        
        # Auto-save group
        autosave_group = QGroupBox("Auto-Save")
        autosave_layout = QFormLayout(autosave_group)
        
        self.auto_export = QCheckBox("Auto-export after transcription")
        autosave_layout.addRow(self.auto_export)
        
        self.auto_save_interval = QSpinBox()
        self.auto_save_interval.setRange(1, 30)
        self.auto_save_interval.setSuffix(" minutes")
        autosave_layout.addRow("Auto-save interval:", self.auto_save_interval)
        
        export_layout.addWidget(autosave_group)
        
        # Export directory
        dir_group = QGroupBox("Export Directory")
        dir_layout = QFormLayout(dir_group)
        
        self.export_dir = QLineEdit()
        self.export_dir.setReadOnly(True)
        export_dir_layout = QHBoxLayout()
        export_dir_layout.addWidget(self.export_dir)
        
        browse_export_btn = QPushButton("Browse...")
        browse_export_btn.clicked.connect(self.browse_export_dir)
        export_dir_layout.addWidget(browse_export_btn)
        
        dir_layout.addRow("Save to:", export_dir_layout)
        
        export_layout.addWidget(dir_group)
        export_layout.addStretch()
        
        tabs.addTab(export_tab, "Export")
        
        # ========== Learning Tab ==========
        learning_tab = QWidget()
        learning_layout = QVBoxLayout(learning_tab)
        
        # Learning mode group
        mode_group = QGroupBox("Continuous Learning")
        mode_layout = QFormLayout(mode_group)
        
        self.learning_enabled = QCheckBox("Enable continuous learning")
        self.learning_enabled.setChecked(True)
        self.learning_enabled.setToolTip("Collect corrections and improve the model over time")
        mode_layout.addRow(self.learning_enabled)
        
        self.auto_train = QCheckBox("Auto-train when idle")
        self.auto_train.setChecked(True)
        self.auto_train.setToolTip("Automatically train when computer is idle")
        mode_layout.addRow(self.auto_train)
        
        self.idle_minutes = QSpinBox()
        self.idle_minutes.setRange(1, 30)
        self.idle_minutes.setValue(5)
        self.idle_minutes.setSuffix(" minutes")
        self.idle_minutes.setToolTip("Time of inactivity before auto-training")
        mode_layout.addRow("Train after idle for:", self.idle_minutes)
        
        learning_layout.addWidget(mode_group)
        
        # Training Parameters Group
        train_params_group = QGroupBox("Training Parameters")
        train_params_layout = QFormLayout(train_params_group)
        
        self.learning_rate = QDoubleSpinBox()
        self.learning_rate.setRange(1e-7, 1e-4)
        self.learning_rate.setDecimals(7)
        self.learning_rate.setSingleStep(1e-6)
        self.learning_rate.setValue(1e-5)
        self.learning_rate.setToolTip("Learning rate for fine-tuning (lower = more stable)")
        train_params_layout.addRow("Learning Rate:", self.learning_rate)
        
        self.num_epochs = QSpinBox()
        self.num_epochs.setRange(1, 10)
        self.num_epochs.setValue(3)
        self.num_epochs.setToolTip("Number of training epochs")
        train_params_layout.addRow("Training Epochs:", self.num_epochs)
        
        self.batch_size = QSpinBox()
        self.batch_size.setRange(1, 16)
        self.batch_size.setValue(4)
        self.batch_size.setToolTip("Batch size for training (higher = faster but more memory)")
        train_params_layout.addRow("Batch Size:", self.batch_size)
        
        self.min_corrections = QSpinBox()
        self.min_corrections.setRange(5, 100)
        self.min_corrections.setValue(10)
        self.min_corrections.setToolTip("Minimum corrections before training")
        train_params_layout.addRow("Min Corrections:", self.min_corrections)
        
        learning_layout.addWidget(train_params_group)
        
        # Data collection group
        data_group = QGroupBox("Data Collection")
        data_layout = QFormLayout(data_group)
        
        self.collect_corrections = QCheckBox("Collect user corrections")
        self.collect_corrections.setChecked(True)
        self.collect_corrections.setToolTip("Save edited transcriptions as training data")
        data_layout.addRow(self.collect_corrections)
        
        self.confidence_threshold = QDoubleSpinBox()
        self.confidence_threshold.setRange(0.0, 1.0)
        self.confidence_threshold.setSingleStep(0.05)
        self.confidence_threshold.setValue(0.7)
        self.confidence_threshold.setToolTip("Only collect corrections when confidence is below this value")
        data_layout.addRow("Min confidence to collect:", self.confidence_threshold)
        
        learning_layout.addWidget(data_group)
        
        # Model management group
        model_group = QGroupBox("Model Management")
        model_layout = QFormLayout(model_group)
        
        self.keep_versions = QSpinBox()
        self.keep_versions.setRange(1, 20)
        self.keep_versions.setValue(5)
        self.keep_versions.setToolTip("Number of trained model versions to keep")
        model_layout.addRow("Keep last N versions:", self.keep_versions)
        
        learning_layout.addWidget(model_group)
        learning_layout.addStretch()
        
        tabs.addTab(learning_tab, "Learning")
        
        layout.addWidget(tabs)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        layout.addWidget(buttons)
        
        # Update cache size after UI is built
        self.update_cache_size()
        if CUDA_AVAILABLE:
            self.update_gpu_memory()
    
    def browse_cache_path(self):
        """Browse for cache directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Model Cache Directory",
            self.cache_path.text()
        )
        if directory:
            self.cache_path.setText(directory)
            self.update_cache_size()
    
    def browse_export_dir(self):
        """Browse for export directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Export Directory",
            self.export_dir.text()
        )
        if directory:
            self.export_dir.setText(directory)
    
    def clear_gpu_cache(self):
        """Clear GPU cache"""
        if CUDA_AVAILABLE:
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            self.update_gpu_memory()
            QMessageBox.information(self, "GPU Cache", "GPU cache cleared successfully!")
    
    def update_gpu_memory(self):
        """Update GPU memory display"""
        if CUDA_AVAILABLE:
            try:
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                free = (torch.cuda.get_device_properties(0).total_memory - 
                       torch.cuda.memory_allocated()) / 1024**3
                self.gpu_memory_label.setText(
                    f"Allocated: {allocated:.2f} GB | Reserved: {reserved:.2f} GB | Free: {free:.2f} GB"
                )
            except:
                self.gpu_memory_label.setText("Unable to read GPU memory")
    
    def update_cache_size(self):
        """Update cache size display"""
        from pathlib import Path
        cache_path = Path(self.cache_path.text())
        if cache_path.exists():
            total_size = 0
            for file in cache_path.rglob("*"):
                if file.is_file():
                    total_size += file.stat().st_size
            size_mb = total_size / (1024 * 1024)
            self.cache_size_label.setText(f"{size_mb:.1f} MB")
        else:
            self.cache_size_label.setText("0 MB")
    
    def load_settings(self):
        """Load settings from config"""
        # Transcription
        self.language_combo.setCurrentText(self.config.get("language", "auto"))
        self.chunk_size.setValue(self.config.get("chunk_duration", 2.5))
        self.overlap.setValue(self.config.get("chunk_overlap", 0.5))
        self.sentence_chunking.setChecked(self.config.get("sentence_chunking", True))
        self.beam_size.setValue(self.config.get("beam_size", 5))
        self.temperature.setValue(self.config.get("temperature", 0.0))
        
        # Performance
        device = self.config.get("device", "auto")
        found = False
        for i in range(self.device_combo.count()):
            if self.device_combo.itemData(i) == device:
                self.device_combo.setCurrentIndex(i)
                found = True
                break
        if not found:
            self.device_combo.setCurrentIndex(0)
        
        compute_type = self.config.get("compute_type", "float32" if CUDA_AVAILABLE else "int8")
        if compute_type in [self.precision_combo.itemText(i) for i in range(self.precision_combo.count())]:
            self.precision_combo.setCurrentText(compute_type)
        
        self.thread_count.setValue(self.config.get("thread_count", 4))
        self.cache_path.setText(self.config.get("model_cache", "./models_cache"))
        
        # Appearance
        self.theme_combo.setCurrentText(self.config.get("theme", "dark"))
        self.font_family.setCurrentText(self.config.get("font_family", "Monospace"))
        self.font_size.setValue(self.config.get("font_size", 11))
        layout_index = self.config.get("layout", 0)
        if layout_index < self.layout_combo.count():
            self.layout_combo.setCurrentIndex(layout_index)

        # Shortcuts
        shortcuts = self.config.get("shortcuts", {})
        for key, editor in self.shortcut_editors.items():
            editor.setKeySequence(shortcuts.get(key, ""))
        
        # Export
        export_format_index = self.config.get("export_format", 0)
        if export_format_index < self.export_format.count():
            self.export_format.setCurrentIndex(export_format_index)
        self.encoding_combo.setCurrentText(self.config.get("encoding", "utf-8"))
        self.auto_export.setChecked(self.config.get("auto_export", True))
        self.auto_save_interval.setValue(self.config.get("auto_save_interval", 5))
        self.export_dir.setText(self.config.get("export_directory", "./output"))
        
        # Learning
        self.learning_enabled.setChecked(self.config.get("learning_enabled", True))
        self.auto_train.setChecked(self.config.get("auto_train", True))
        self.idle_minutes.setValue(self.config.get("idle_minutes", 5))
        self.collect_corrections.setChecked(self.config.get("collect_corrections", True))
        self.confidence_threshold.setValue(self.config.get("confidence_threshold", 0.7))
        self.keep_versions.setValue(self.config.get("keep_versions", 5))
        
        # Training Parameters
        self.learning_rate.setValue(self.config.get("learning_rate", 1e-5))
        self.num_epochs.setValue(self.config.get("num_epochs", 3))
        self.batch_size.setValue(self.config.get("batch_size", 4))
        self.min_corrections.setValue(self.config.get("min_corrections_for_training", 10))
    
    def save_settings(self):
        """Save settings to config"""
        if self.apply_settings():
            self.accept()
    
    def apply_settings(self):
        """Apply settings without closing dialog"""
        conflicts = self._find_shortcut_conflicts()
        if conflicts:
            details = "\n".join(
                f"{sequence}: {first} and {second}"
                for sequence, first, second in conflicts
            )
            QMessageBox.warning(
                self,
                "Shortcut Conflict",
                "Please resolve duplicate shortcut assignments before saving:\n\n"
                f"{details}"
            )
            return False

        # Transcription
        self.config.set("language", self.language_combo.currentText())
        self.config.set("chunk_duration", self.chunk_size.value())
        self.config.set("chunk_overlap", self.overlap.value())
        self.config.set("sentence_chunking", self.sentence_chunking.isChecked())
        self.config.set("beam_size", self.beam_size.value())
        self.config.set("temperature", self.temperature.value())
        
        # Performance
        device_value = self.device_combo.currentData()
        self.config.set("device", device_value)
        self.config.set("compute_type", self.precision_combo.currentText())
        self.config.set("thread_count", self.thread_count.value())
        self.config.set("model_cache", self.cache_path.text())
        
        # Appearance
        self.config.set("theme", self.theme_combo.currentText())
        self.config.set("font_family", self.font_family.currentText())
        self.config.set("font_size", self.font_size.value())
        self.config.set("layout", self.layout_combo.currentIndex())

        # Shortcuts
        shortcuts = {}
        for key, editor in self.shortcut_editors.items():
            shortcuts[key] = editor.keySequence().toString()
        self.config.set("shortcuts", shortcuts)
        
        # Export
        self.config.set("export_format", self.export_format.currentIndex())
        self.config.set("encoding", self.encoding_combo.currentText())
        self.config.set("auto_export", self.auto_export.isChecked())
        self.config.set("auto_save_interval", self.auto_save_interval.value())
        self.config.set("export_directory", self.export_dir.text())
        
        # Learning
        self.config.set("learning_enabled", self.learning_enabled.isChecked())
        self.config.set("auto_train", self.auto_train.isChecked())
        self.config.set("idle_minutes", self.idle_minutes.value())
        self.config.set("collect_corrections", self.collect_corrections.isChecked())
        self.config.set("confidence_threshold", self.confidence_threshold.value())
        self.config.set("keep_versions", self.keep_versions.value())
        
        # Training Parameters
        self.config.set("learning_rate", self.learning_rate.value())
        self.config.set("num_epochs", self.num_epochs.value())
        self.config.set("batch_size", self.batch_size.value())
        self.config.set("min_corrections_for_training", self.min_corrections.value())
        
        self.config.save()
        self.settings_changed.emit()
        return True

    def _find_shortcut_conflicts(self):
        """Return duplicate shortcut assignments."""
        seen = {}
        conflicts = []

        for key, editor in self.shortcut_editors.items():
            sequence = editor.keySequence().toString().strip()
            if not sequence:
                continue

            label = key.replace("_", " ").title()
            previous = seen.get(sequence)
            if previous:
                conflicts.append((sequence, previous, label))
            else:
                seen[sequence] = label

        return conflicts
