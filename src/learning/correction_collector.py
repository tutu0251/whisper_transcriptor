"""
Correction Collector Module
Collect user edits as training data
"""

import hashlib
import time
from typing import Optional


class CorrectionCollector:
    """Collect and store user corrections"""
    
    def __init__(self, database_manager):
        self.db = database_manager
        self.pending_count = 0
        self.confidence_threshold = 0.7
    
    def collect_correction(self, audio_segment, original: str, corrected: str, 
                           confidence: float, language: str = "en",
                           file_path: str = None, start_time: float = 0,
                           end_time: float = 0) -> bool:
        """Collect a user correction"""
        # Only collect if confidence was low (user fixed a real error)
        if confidence > self.confidence_threshold:
            return False
        
        # Generate audio hash
        audio_hash = self._hash_audio(audio_segment)
        
        # Check for duplicate
        if self._is_duplicate(audio_hash, corrected):
            return False
        
        # Store correction
        correction_data = {
            "audio_hash": audio_hash,
            "original_text": original,
            "corrected_text": corrected,
            "confidence": confidence,
            "language": language,
            "file_path": file_path,
            "start_time": start_time,
            "end_time": end_time
        }
        
        self.db.add_correction(correction_data)
        self.pending_count += 1
        
        return True
    
    def _hash_audio(self, audio_segment) -> str:
        """Create hash from audio segment"""
        # Simplified: use sample data
        import numpy as np
        if hasattr(audio_segment, 'get_array_of_samples'):
            samples = audio_segment.get_array_of_samples()
            data = np.array(samples)
            return hashlib.md5(data.tobytes()).hexdigest()
        return hashlib.md5(str(time.time()).encode()).hexdigest()
    
    def _is_duplicate(self, audio_hash: str, corrected_text: str) -> bool:
        """Check if this correction already exists"""
        # Simplified duplicate detection
        return False
    
    def get_pending_count(self) -> int:
        """Get number of pending corrections"""
        return self.pending_count
    
    def reset_pending(self):
        """Reset pending counter"""
        self.pending_count = 0
