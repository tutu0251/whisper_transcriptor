#!/usr/bin/env python3
"""
Video/Audio Transcriber with Local Whisper Models
Real-time transcription, SRT export, and continuous learning
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.utils.config import Config
from src.gui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("Video Audio Transcriber")
    app.setOrganizationName("TranscriberApp")
    
    config = Config()
    window = MainWindow(config)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
