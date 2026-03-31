"""
SRT Editor Module
Advanced SRT editing with timeline
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QSpinBox, QLabel
from PyQt6.QtCore import Qt


class SRTEditor(QWidget):
    """Advanced SRT editor with timeline adjustment"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Timeline offset controls
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Timeline Offset (ms):"))
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-5000, 5000)
        self.offset_spin.setSuffix(" ms")
        offset_layout.addWidget(self.offset_spin)
        
        self.apply_offset_btn = QPushButton("Apply Offset")
        offset_layout.addWidget(self.apply_offset_btn)
        offset_layout.addStretch()
        
        layout.addLayout(offset_layout)
        
        # SRT content editor
        self.text_edit = QTextEdit()
        self.text_edit.setFontFamily("Monospace")
        layout.addWidget(self.text_edit)
    
    def load_srt(self, content: str):
        """Load SRT content"""
        self.text_edit.setText(content)
    
    def get_srt(self) -> str:
        """Get current SRT content"""
        return self.text_edit.toPlainText()
    
    def apply_offset(self):
        """Apply timeline offset to all timestamps"""
        # TODO: Implement timestamp offset
        pass
