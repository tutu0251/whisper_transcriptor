"""
Correction Collector Module - Store audio paths for real training
"""

import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime


class CorrectionCollector:
    """Collect and store user corrections with audio paths for training"""
    
    def __init__(self, database_manager):
        self.db = database_manager
        self.pending_count = 0
        self.confidence_threshold = 0.7
        self.enabled = True
        self.min_text_length = 3
        self.max_text_length = 500
        print("✅ CorrectionCollector initialized")
    
    def collect_correction(self, audio_segment, original: str, corrected: str, 
                           confidence: float, language: str = "en",
                           file_path: str = None, start_time: float = 0,
                           end_time: float = 0) -> bool:
        """
        Collect a user correction with full audio path for real training
        
        Args:
            audio_segment: Audio segment (can be None if not available)
            original: Original text before correction
            corrected: Corrected text after edit
            confidence: Model confidence (0-1)
            language: Language code
            file_path: Source audio file path (REQUIRED for training)
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            True if correction was stored
        """
        if not self.enabled:
            print("⚠️ Correction collector is disabled")
            return False
        
        print(f"📝 Collecting correction:")
        print(f"   Original: '{original[:50]}...'")
        print(f"   Corrected: '{corrected[:50]}...'")
        print(f"   Confidence: {confidence:.2f}")
        print(f"   File: {file_path}")
        print(f"   Time: {start_time:.1f}s - {end_time:.1f}s")
        
        # Validate correction quality
        is_valid, reason = self._validate_correction(original, corrected, confidence)
        if not is_valid:
            print(f"⚠️ Correction rejected: {reason}")
            return False
        
        # Don't collect if no meaningful change
        if original.strip() == corrected.strip():
            print("⚠️ Skipping correction (no change)")
            return False
        
        # Check if file path exists (required for training)
        if file_path and not self._file_exists(file_path):
            print(f"⚠️ Audio file not found: {file_path}")
            return False
        
        # Generate audio hash
        audio_hash = self._hash_audio(audio_segment)
        
        # Store correction with full file path
        correction_data = {
            "audio_hash": audio_hash,
            "original_text": original,
            "corrected_text": corrected,
            "confidence": confidence,
            "language": language,
            "file_path": file_path or "",
            "start_time": start_time,
            "end_time": end_time
        }
        
        try:
            correction_id = self.db.add_correction(correction_data)
            self.pending_count += 1
            print(f"✅ Correction stored (ID: {correction_id})")
            print(f"   '{original[:30]}' → '{corrected[:30]}'")
            return True
        except Exception as e:
            print(f"❌ Failed to store correction: {e}")
            return False
    
    def _validate_correction(self, original: str, corrected: str, confidence: float) -> tuple:
        """Validate a correction for quality"""
        if len(corrected.strip()) < self.min_text_length:
            return False, f"Text too short ({len(corrected.strip())} chars)"
        
        if len(corrected) > self.max_text_length:
            return False, f"Text too long ({len(corrected)} chars)"
        
        # Only collect low confidence corrections (user fixed a real error)
        if confidence > self.confidence_threshold:
            return False, f"Confidence too high ({confidence:.2f} > {self.confidence_threshold})"
        
        # Check if correction is meaningful
        if len(original) > 0 and len(corrected) > 0:
            similarity = self._calculate_similarity(original, corrected)
            if similarity > 0.95:
                return False, f"Minimal change (similarity {similarity:.2f})"
        
        # Check for gibberish
        if self._is_gibberish(corrected):
            return False, "Text appears to be gibberish"
        
        return True, "Valid"
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _is_gibberish(self, text: str) -> bool:
        """Check if text appears to be gibberish"""
        import re
        
        # Check for excessive repetition
        if re.search(r'(.)\1{5,}', text):
            return True
        
        # Check for random characters
        non_alnum = len(re.findall(r'[^a-zA-Z0-9\s\.,!?;:\'\"\-]', text))
        if non_alnum > len(text) * 0.3:
            return True
        
        # Check for very long words
        words = text.split()
        for word in words:
            if len(word) > 30:
                return True
        
        return False
    
    def _hash_audio(self, audio_segment) -> str:
        """Create hash from audio segment"""
        import numpy as np
        
        if audio_segment is not None:
            try:
                if isinstance(audio_segment, np.ndarray):
                    return hashlib.md5(audio_segment.tobytes()).hexdigest()
                elif hasattr(audio_segment, 'tobytes'):
                    return hashlib.md5(audio_segment.tobytes()).hexdigest()
            except Exception:
                pass
        
        return hashlib.md5(str(time.time()).encode()).hexdigest()
    
    def _file_exists(self, file_path: str) -> bool:
        """Check if audio file exists"""
        import os
        return os.path.exists(file_path)
    
    def get_pending_count(self) -> int:
        """Get number of pending corrections"""
        if self.db:
            stats = self.db.get_statistics()
            return stats.get('pending_corrections', 0)
        return self.pending_count
    
    def reset_pending(self):
        """Reset pending counter"""
        self.pending_count = 0
    
    def enable(self):
        """Enable correction collection"""
        self.enabled = True
        print("✅ Correction collector enabled")
    
    def disable(self):
        """Disable correction collection"""
        self.enabled = False
        print("⚠️ Correction collector disabled")
    
    def set_confidence_threshold(self, threshold: float):
        """Set confidence threshold"""
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        print(f"📊 Confidence threshold set to: {self.confidence_threshold}")
    
    def get_stats(self) -> Dict:
        """Get collector statistics"""
        if self.db:
            return self.db.get_statistics()
        return {
            "pending": self.pending_count,
            "enabled": self.enabled,
            "confidence_threshold": self.confidence_threshold
        }