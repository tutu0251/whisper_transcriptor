"""
Playback State Model
Data structure for current playback state
"""

from dataclasses import dataclass
from enum import Enum


class PlaybackMode(Enum):
    """Playback mode"""
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class DisplayMode(Enum):
    """Transcription display mode"""
    LIVE = "live"
    SRT = "srt"
    EDIT = "edit"


@dataclass
class PlaybackState:
    """Current playback state"""
    mode: PlaybackMode = PlaybackMode.STOPPED
    display_mode: DisplayMode = DisplayMode.LIVE
    current_time: float = 0.0
    total_duration: float = 0.0
    volume: int = 70
    speed: float = 1.0
    current_file: str = ""
    has_srt: bool = False
