"""
Utils Module
Contains utility functions and helper classes.
"""

from src.utils.file_utils import get_media_files, find_srt_file, get_file_size, format_file_size
from src.utils.timestamp_utils import seconds_to_srt_time, srt_time_to_seconds, format_time_display

# Audio utils (optional - requires numpy)
try:
    from src.utils.audio_utils import normalize_audio, resample_audio, convert_to_mono, trim_silence
    AUDIO_UTILS_AVAILABLE = True
except ImportError:
    AUDIO_UTILS_AVAILABLE = False
    # Provide dummy functions
    def normalize_audio(*args, **kwargs): return None
    def resample_audio(*args, **kwargs): return None
    def convert_to_mono(*args, **kwargs): return None
    def trim_silence(*args, **kwargs): return None

from src.utils.config import Config
from src.utils.logger import setup_logger, get_logger

__all__ = [
    # File utilities
    "get_media_files",
    "find_srt_file",
    "get_file_size",
    "format_file_size",
    
    # Timestamp utilities
    "seconds_to_srt_time",
    "srt_time_to_seconds",
    "format_time_display",
    
    # Audio utilities
    "normalize_audio",
    "resample_audio",
    "convert_to_mono",
    "trim_silence",
    
    # Config and logging
    "Config",
    "setup_logger",
    "get_logger",
]