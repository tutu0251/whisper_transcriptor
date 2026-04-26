"""
Status Bar Module
Display status information and progress
"""

from PyQt6.QtWidgets import QLabel, QProgressBar, QSizePolicy, QStatusBar
from PyQt6.QtCore import Qt


class StatusBar(QStatusBar):
    """Custom status bar with progress"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        self.setSizeGripEnabled(True)
        self.setFixedHeight(22)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.addWidget(self.status_label, 1)

        self.model_label = QLabel("")
        self.language_label = QLabel("Lang: AUTO")
        self.correction_label = QLabel("0 pending | 0 trained")
        self.training_label = QLabel("Training: idle")

        for label in (
            self.model_label,
            self.language_label,
            self.correction_label,
            self.training_label,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.addPermanentWidget(label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setVisible(False)
        self.addPermanentWidget(self.progress_bar)
    
    def set_status(self, text: str):
        """Set status text"""
        self.status_label.setText(text)
    
    def set_model(self, model_name: str):
        """Set model name"""
        self.model_label.setText(f"Model : {model_name}" if model_name else "")

    def set_language(self, language: str):
        """Set language text"""
        self.language_label.setText(f"Lang: {language.upper()}")

    def set_corrections(self, pending: int, trained: int):
        """Set correction counts"""
        self.correction_label.setText(f"{pending} pending | {trained} trained")

    def set_training(self, text: str):
        """Set training status text"""
        self.training_label.setText(f"Training: {text}")
    
    def show_progress(self, visible: bool):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(visible)
    
    def set_progress(self, value: int, maximum: int = 100):
        """Set progress value"""
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(value)
