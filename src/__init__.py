"""
Video/Audio Transcriber
A powerful desktop application for transcribing video and audio files using local Whisper models.

This package provides:
- Real-time transcription with local Whisper models
- SRT subtitle import/export
- Continuous learning from user corrections
- Model training and fine-tuning
- Multi-language support (99+ languages)
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"
__license__ = "MIT"
__copyright__ = f"Copyright (c) 2025 {__author__}"

# Package metadata
PACKAGE_NAME = "video_audio_transcriber"
PACKAGE_DESCRIPTION = "Transcribe video/audio with local Whisper models"
PACKAGE_URL = "https://github.com/yourusername/video_audio_transcriber"

# Export main classes for easier imports
from src.core.transcriber import Transcriber
from src.core.srt_handler import SRTHandler, SRTEntry
from src.core.model_manager import ModelManager
from src.utils.config import Config

try:
    from src.core.media_player import MediaPlayer
except Exception:
    MediaPlayer = None

# Define what gets imported with "from src import *"
__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    
    # Core classes
    "Transcriber", 
    "SRTHandler",
    "SRTEntry",
    "ModelManager",
    "Config",
]

if MediaPlayer is not None:
    __all__.insert(3, "MediaPlayer")

__all__.extend([
    # Package info
    "PACKAGE_NAME",
    "PACKAGE_DESCRIPTION",
    "PACKAGE_URL",
])

# Optional: Print version on import (can be disabled with environment variable)
import os
if os.environ.get("TRANSCRIBER_VERBOSE", "").lower() == "true":
    print(f"📦 {PACKAGE_NAME} version {__version__} loaded")