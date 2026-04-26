"""
Model Manager Dialog Module
Download, manage, and register custom models
"""

import shutil
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLabel, QProgressBar, QMessageBox,
    QFileDialog, QListWidgetItem, QWidget, QTabWidget,
    QGroupBox, QFormLayout, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from src.core.model_manager import ModelManager


class ModelManagerDialog(QDialog):
    """Model manager dialog for Hugging Face model management"""
    
    model_changed = pyqtSignal(str)  # Signal when model is selected/changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_manager = ModelManager()
        self.setWindowTitle("Model Manager")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        self.setup_ui()
        self.refresh_models()
    
    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # ========== HF Models Tab ==========
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        
        # Info label
        custom_info = QLabel("Hugging Face Models")
        custom_info.setStyleSheet("font-weight: bold; margin: 5px;")
        custom_layout.addWidget(custom_info)
        
        # Custom models list
        self.custom_list = QListWidget()
        self.custom_list.itemDoubleClicked.connect(self.use_custom_model)
        custom_layout.addWidget(self.custom_list)
        
        # Buttons
        custom_buttons = QHBoxLayout()
        
        self.register_btn = QPushButton("📁 Register Custom Model")
        self.register_btn.clicked.connect(self.register_custom_model)
        custom_buttons.addWidget(self.register_btn)
        
        self.use_custom_btn = QPushButton("✅ Use This Model")
        self.use_custom_btn.clicked.connect(self.use_custom_model)
        custom_buttons.addWidget(self.use_custom_btn)
        
        self.delete_custom_btn = QPushButton("🗑️ Delete")
        self.delete_custom_btn.clicked.connect(self.delete_custom_model)
        custom_buttons.addWidget(self.delete_custom_btn)
        
        custom_buttons.addStretch()
        custom_layout.addLayout(custom_buttons)
        
        # Requirements info
        req_group = QGroupBox("Custom Model Requirements")
        req_layout = QVBoxLayout(req_group)
        
        req_layout.addWidget(QLabel("Your custom model folder must contain:"))
        req_layout.addWidget(QLabel("  • config.json"))
        req_layout.addWidget(QLabel("  • model.safetensors (or pytorch_model.bin)"))
        req_layout.addWidget(QLabel("  • tokenizer.json"))
        req_layout.addWidget(QLabel("  • tokenizer_config.json"))
        req_layout.addWidget(QLabel("  • processor_config.json (optional)"))
        
        custom_layout.addWidget(req_group)
        
        tabs.addTab(custom_tab, "HF Models")
        
        layout.addWidget(tabs)
        
        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; margin: 5px;")
        layout.addWidget(self.status_label)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def refresh_models(self):
        """Refresh the model list"""
        models = self.model_manager.list_models()
        
        # Clear HF model list
        self.custom_list.clear()
        
        for model in models:
            if model.type != "custom":
                continue
                
            size_text = f"{model.size_mb:.1f} MB"
            item_text = f"{model.name} ({size_text})"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, model.name)
            item.setData(Qt.ItemDataRole.UserRole + 1, "custom")
            
            self.custom_list.addItem(item)
        
        # Update status
        total_size = self.model_manager.get_cache_size() / (1024 * 1024)
        self.status_label.setText(f"Total cache size: {total_size:.1f} MB")
    
    def download_model(self):
        """Download selected standard model"""
        if not hasattr(self, 'standard_list'):
            QMessageBox.warning(self, "Unavailable", "Standard model download is not available.")
            return
        current = self.standard_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a model to download.")
            return
        
        model_name = current.data(Qt.ItemDataRole.UserRole)
        
        if self.model_manager.is_model_downloaded(model_name):
            QMessageBox.information(self, "Already Downloaded", f"Model {model_name} is already downloaded.")
            return
        
        # Confirm download
        size_mb = self.model_manager.get_model_size_mb(model_name)
        reply = QMessageBox.question(
            self,
            "Confirm Download",
            f"Download {model_name.upper()} ({size_mb:.0f} MB)?\n\nThis may take a few minutes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText(f"Downloading {model_name}...")
            
            # Simple progress callback
            def progress_callback(current, total):
                percent = int(current / total * 100)
                self.status_label.setText(f"Downloading {model_name}: {percent}%")
                QApplication.processEvents()
            
            success = self.model_manager.download_model(model_name, progress_callback)
            
            if success:
                self.status_label.setText(f"✅ Model {model_name} downloaded successfully!")
                QMessageBox.information(self, "Download Complete", f"Model {model_name} downloaded successfully!")
                self.refresh_models()
            else:
                self.status_label.setText(f"❌ Failed to download {model_name}")
                QMessageBox.critical(self, "Download Failed", f"Failed to download {model_name}.")
    
    def use_model(self):
        """Use selected standard model"""
        if not hasattr(self, 'standard_list'):
            QMessageBox.warning(self, "Unavailable", "Standard model selection is not available.")
            return
        current = self.standard_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a model to use.")
            return
        
        model_name = current.data(Qt.ItemDataRole.UserRole)
        
        if not self.model_manager.is_model_downloaded(model_name):
            QMessageBox.warning(self, "Model Not Downloaded", f"Model {model_name} is not downloaded. Please download it first.")
            return
        
        # Emit signal to use this model
        self.model_changed.emit(model_name)
        self.status_label.setText(f"✅ Using model: {model_name}")
        
        QMessageBox.information(self, "Model Selected", f"Using model: {model_name.upper()}\n\nRestart transcription to apply changes.")
    
    def delete_model(self):
        """Delete selected standard model"""
        if not hasattr(self, 'standard_list'):
            QMessageBox.warning(self, "Unavailable", "Standard model delete is not available.")
            return
        current = self.standard_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a model to delete.")
            return
        
        model_name = current.data(Qt.ItemDataRole.UserRole)
        
        if not self.model_manager.is_model_downloaded(model_name):
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete model {model_name.upper()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.model_manager.delete_model(model_name):
                self.status_label.setText(f"✅ Model {model_name} deleted.")
                self.refresh_models()
            else:
                self.status_label.setText(f"❌ Failed to delete {model_name}")
                QMessageBox.critical(self, "Error", f"Failed to delete {model_name}.")
    
    def register_custom_model(self):
        """Register a custom model folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Custom Model Folder",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if not folder_path:
            return
        
        # Check if folder contains required files
        required_files = ["config.json", "tokenizer_config.json"]
        optional_files = ["model.safetensors", "pytorch_model.bin", "processor_config.json"]
        
        missing = []
        for file in required_files:
            if not (Path(folder_path) / file).exists():
                missing.append(file)
        
        # Check if at least one model file exists
        has_model = False
        for file in optional_files:
            if (Path(folder_path) / file).exists():
                has_model = True
                break
        
        if not has_model:
            missing.append("model.safetensors or pytorch_model.bin")
        
        if missing:
            QMessageBox.warning(
                self,
                "Invalid Model Folder",
                f"The selected folder is missing required files:\n\n" + "\n".join(missing) +
                "\n\nMake sure the folder contains a valid Hugging Face Whisper model."
            )
            return
        
        # Ask for model name
        model_name, ok = QInputDialog.getText(
            self,
            "Model Name",
            "Enter a name for this model:",
            text=Path(folder_path).name
        )
        
        if not ok or not model_name:
            return
        
        # Register model
        try:
            registered_name = self.model_manager.register_custom_model(folder_path, model_name)
            self.status_label.setText(f"✅ Custom model '{registered_name}' registered!")
            QMessageBox.information(self, "Success", f"Custom model '{registered_name}' registered successfully!")
            self.refresh_models()
        except Exception as e:
            self.status_label.setText(f"❌ Failed to register model: {e}")
            QMessageBox.critical(self, "Error", f"Failed to register model:\n{str(e)}")
    
    def use_custom_model(self):
        """Use selected custom model"""
        current = self.custom_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a custom model to use.")
            return
        
        model_name = current.data(Qt.ItemDataRole.UserRole)
        custom_path = self.model_manager.get_custom_model_path(model_name)
        
        if not custom_path.exists():
            QMessageBox.warning(self, "Model Not Found", f"Model '{model_name}' not found.")
            return
        
        # Emit signal with the model path
        self.model_changed.emit(str(custom_path))
        self.status_label.setText(f"✅ Using custom model: {model_name}")
        
        QMessageBox.information(self, "Model Selected", f"Using custom model: {model_name}\n\nPath: {custom_path}\n\nRestart transcription to apply changes.")
    
    def delete_custom_model(self):
        """Delete selected custom model"""
        current = self.custom_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a custom model to delete.")
            return
        
        model_name = current.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete custom model '{model_name}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.model_manager.delete_model(model_name):
                self.status_label.setText(f"✅ Custom model '{model_name}' deleted.")
                self.refresh_models()
            else:
                self.status_label.setText(f"❌ Failed to delete '{model_name}'")
                QMessageBox.critical(self, "Error", f"Failed to delete '{model_name}'.")


# Add QApplication import if needed
from PyQt6.QtWidgets import QApplication