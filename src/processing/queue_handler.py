"""
Queue Handler Module
Manage audio and transcription queues
"""

import queue
from typing import Optional


class QueueHandler:
    """Queue handler for audio and transcription data"""
    
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.error_queue = queue.Queue()
    
    def add_audio(self, audio_chunk):
        """Add audio chunk to queue"""
        self.audio_queue.put(audio_chunk)
    
    def get_audio(self, timeout: Optional[float] = None):
        """Get audio chunk from queue"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def add_transcription(self, text: str, start: float, end: float):
        """Add transcription result to queue"""
        self.transcription_queue.put({
            "text": text,
            "start": start,
            "end": end
        })
    
    def get_transcription(self, timeout: Optional[float] = None):
        """Get transcription from queue"""
        try:
            return self.transcription_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def add_error(self, error: Exception):
        """Add error to queue"""
        self.error_queue.put(error)
    
    def clear(self):
        """Clear all queues"""
        while not self.audio_queue.empty():
            self.audio_queue.get()
        while not self.transcription_queue.empty():
            self.transcription_queue.get()
        while not self.error_queue.empty():
            self.error_queue.get()
