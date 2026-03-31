"""
Audio Extractor Module
Extract audio from video files for transcription
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


class AudioExtractor:
    """Extract audio from video files"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "transcriber_audio"
        self.temp_dir.mkdir(exist_ok=True)
    
    def extract_audio(self, video_path: str, output_path: str = None) -> Optional[str]:
        """Extract audio from video file"""
        if not PYDUB_AVAILABLE:
            return None
        
        if not os.path.exists(video_path):
            return None
        
        if output_path is None:
            video_name = Path(video_path).stem
            output_path = self.temp_dir / f"{video_name}.wav"
        else:
            output_path = Path(output_path)
        
        try:
            audio = AudioSegment.from_file(video_path)
            audio.export(str(output_path), format="wav")
            return str(output_path)
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None
    
    def get_audio_duration(self, file_path: str) -> float:
        """Get duration of audio file in seconds"""
        try:
            audio = AudioSegment.from_file(file_path)
            return len(audio) / 1000.0
        except Exception:
            return 0.0
    
    def split_audio(self, audio_path: str, chunk_duration: float, 
                    overlap: float = 0.5) -> list:
        """Split audio into overlapping chunks"""
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)
        chunk_ms = int(chunk_duration * 1000)
        overlap_ms = int(overlap * 1000)
        step_ms = chunk_ms - overlap_ms
        
        chunks = []
        for start_ms in range(0, duration_ms, step_ms):
            end_ms = min(start_ms + chunk_ms, duration_ms)
            chunk = audio[start_ms:end_ms]
            chunks.append({
                "audio": chunk,
                "start": start_ms / 1000.0,
                "end": end_ms / 1000.0
            })
        
        return chunks
    
    def cleanup(self):
        """Clean up temporary audio files"""
        for file in self.temp_dir.glob("*.wav"):
            try:
                file.unlink()
            except Exception:
                pass
