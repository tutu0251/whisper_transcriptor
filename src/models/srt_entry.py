"""
SRT Entry Model
Data structure for SRT subtitle entry
"""

from dataclasses import dataclass


@dataclass
class SRTEntry:
    """Single SRT subtitle entry"""
    index: int
    start_time: float
    end_time: float
    text: str
    
    def to_timestamp_string(self) -> str:
        """Convert to SRT timestamp format"""
        from src.utils.timestamp_utils import seconds_to_srt_time
        return f"{seconds_to_srt_time(self.start_time)} --> {seconds_to_srt_time(self.end_time)}"
    
    def to_text(self) -> str:
        """Convert to SRT formatted text"""
        return f"{self.index}\n{self.to_timestamp_string()}\n{self.text}"
