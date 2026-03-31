"""
Chunk Manager Module
Split audio into overlapping chunks for transcription
"""

from typing import List, Dict
import numpy as np


class ChunkManager:
    """Manages audio chunking for real-time transcription"""
    
    def __init__(self, chunk_duration: float = 2.5, overlap: float = 0.5):
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.chunks = []
    
    def split_audio(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict]:
        """Split audio into overlapping chunks"""
        chunk_samples = int(self.chunk_duration * sample_rate)
        overlap_samples = int(self.overlap * sample_rate)
        step_samples = chunk_samples - overlap_samples
        
        chunks = []
        for start in range(0, len(audio_data), step_samples):
            end = min(start + chunk_samples, len(audio_data))
            chunk = audio_data[start:end]
            
            chunks.append({
                "data": chunk,
                "start_time": start / sample_rate,
                "end_time": end / sample_rate,
                "sample_rate": sample_rate
            })
            
            if end == len(audio_data):
                break
        
        return chunks
    
    def set_chunk_duration(self, duration: float):
        """Set chunk duration"""
        self.chunk_duration = duration
    
    def set_overlap(self, overlap: float):
        """Set chunk overlap"""
        self.overlap = overlap
