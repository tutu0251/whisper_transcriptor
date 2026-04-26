"""
Core Module
Contains the main functionality for media playback, transcription, and SRT handling.
"""

from src.core.transcriber import Transcriber
from src.core.srt_handler import SRTHandler, SRTEntry
from src.core.model_manager import ModelManager

try:
    from src.core.media_player import MediaPlayer
except Exception:
    MediaPlayer = None

try:
    from src.core.audio_extractor import AudioExtractor
except Exception:
    AudioExtractor = None

__all__ = [
    "Transcriber",
    "SRTHandler",
    "SRTEntry",
    "ModelManager",
]

if MediaPlayer is not None:
    __all__.insert(0, "MediaPlayer")
if AudioExtractor is not None:
    __all__.append("AudioExtractor")
