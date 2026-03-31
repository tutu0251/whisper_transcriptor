"""
Status Bar Module
Display status information and progress
"""

from PyQt6.QtWidgets import QStatusBar, QProgressBar, QLabel
from PyQt6.QtCore import Qt


class StatusBar(QStatusBar):
    """Custom status bar with progress"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        # Status label
        self.status_label = QLabel("Ready")
        self.addWidget(self.status_label)
        
        self.addPermanentWidget(QLabel("|"))
        
        # Model indicator
        self.model_label = QLabel("Model: not loaded")
        self.addPermanentWidget(self.model_label)
        
        self.addPermanentWidget(QLabel("|"))
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setVisible(False)
        self.addPermanentWidget(self.progress_bar)
    
    def set_status(self, text: str):
        """Set status text"""
        self.status_label.setText(text)
    
    def set_model(self, model_name: str):
        """Set model name"""
        self.model_label.setText(f"Model: {model_name}")
    
    def show_progress(self, visible: bool):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(visible)
    
    def set_progress(self, value: int, maximum: int = 100):
        """Set progress value"""
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(value)
