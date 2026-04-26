#!/usr/bin/env python3
"""
Video/Audio Transcriber with Local Whisper Models
Real-time transcription, SRT export, and continuous learning
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Configure VLC for 64-bit compatibility
vlc64_dir = r"C:\Program Files\VideoLAN\VLC"
if os.path.exists(vlc64_dir):
    os.environ['VLC_PLUGIN_PATH'] = vlc64_dir
    # Add 64-bit VLC to PATH first
    current_path = os.environ.get('PATH', '')
    if vlc64_dir not in current_path:
        os.environ['PATH'] = f"{vlc64_dir};{current_path}"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.utils.config import Config

try:
    from src.gui.main_window import MainWindow
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False
    print("GUI components not available - missing dependencies (vlc, etc.)")


def main():
    if not GUI_AVAILABLE:
        print("Cannot start GUI application - required dependencies not available.")
        print("Please install missing dependencies:")
        print("  - VLC media player")
        print("  - Other GUI dependencies")
        return
    
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
