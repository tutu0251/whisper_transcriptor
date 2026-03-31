"""
Transcription Segment Model
Data structure for transcribed chunk
"""

from dataclasses import dataclass


@dataclass
class TranscriptionSegment:
    """Single transcription segment"""
    text: str
    start_time: float
    end_time: float
    confidence: float = 0.0
    language: str = "en"
    
    def to_srt_entry(self, index: int):
        """Convert to SRT entry"""
        from src.models.srt_entry import SRTEntry
        return SRTEntry(
            index=index,
            start_time=self.start_time,
            end_time=self.end_time,
            text=self.text
        )
    
    def duration(self) -> float:
        """Get segment duration"""
        return self.end_time - self.start_time
