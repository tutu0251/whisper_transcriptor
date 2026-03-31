"""
Media File Model
Data structure for media file information
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MediaFile:
    """Media file metadata"""
    path: str
    duration: float = 0.0
    format: str = ""
    has_video: bool = False
    has_audio: bool = True
    width: int = 0
    height: int = 0
    audio_sample_rate: int = 0
    
    @property
    def filename(self) -> str:
        return Path(self.path).name
    
    @property
    def basename(self) -> str:
        return Path(self.path).stem
    
    @property
    def srt_path(self) -> Optional[str]:
        """Get associated SRT file path"""
        srt = Path(self.path).with_suffix(".srt")
        if srt.exists():
            return str(srt)
        return None
