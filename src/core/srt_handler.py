"""
SRT Handler Module
Parse, generate, and export SRT subtitle files
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import timedelta


@dataclass
class SRTEntry:
    """Single SRT subtitle entry"""
    index: int
    start_time: float
    end_time: float
    text: str


class SRTHandler:
    """Handles SRT file operations"""
    
    def __init__(self):
        self.entries: List[SRTEntry] = []
    
    @staticmethod
    def seconds_to_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp format"""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        secs = td.seconds % 60
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    @staticmethod
    def srt_time_to_seconds(srt_time: str) -> float:
        """Convert SRT timestamp to seconds"""
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        match = re.match(pattern, srt_time)
        if match:
            hours, minutes, seconds, millis = map(int, match.groups())
            return hours * 3600 + minutes * 60 + seconds + millis / 1000
        return 0.0
    
    def parse_srt(self, content: str) -> List[SRTEntry]:
        """Parse SRT file content"""
        entries = []
        blocks = content.strip().split('\n\n')
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                try:
                    index = int(lines[0])
                    time_line = lines[1]
                    text = '\n'.join(lines[2:])
                    
                    time_match = re.match(r'(.+) --> (.+)', time_line)
                    if time_match:
                        start = self.srt_time_to_seconds(time_match.group(1))
                        end = self.srt_time_to_seconds(time_match.group(2))
                        
                        entries.append(SRTEntry(
                            index=index,
                            start_time=start,
                            end_time=end,
                            text=text
                        ))
                except (ValueError, IndexError):
                    continue
        
        self.entries = entries
        return entries
    
    def load_file(self, file_path: str) -> List[SRTEntry]:
        """Load SRT from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return self.parse_srt(f.read())
    
    def generate_srt(self, entries: List[SRTEntry]) -> str:
        """Generate SRT content from entries"""
        lines = []
        for entry in entries:
            lines.append(str(entry.index))
            lines.append(f"{self.seconds_to_srt_time(entry.start_time)} --> {self.seconds_to_srt_time(entry.end_time)}")
            lines.append(entry.text)
            lines.append('')
        return '\n'.join(lines)
    
    def save_file(self, file_path: str, entries: List[SRTEntry]) -> bool:
        """Save SRT to file"""
        try:
            content = self.generate_srt(entries)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error saving SRT: {e}")
            return False
