"""
Data Quality Module
Filter and validate training data quality
"""

import re
from typing import List, Dict, Tuple


class DataQuality:
    """Validate and filter training data quality"""
    
    def __init__(self):
        self.min_text_length = 3
        self.max_text_length = 500
        self.min_confidence = 0.3
        self.max_duplicates = 3
    
    def validate_correction(self, original: str, corrected: str, confidence: float) -> Tuple[bool, str]:
        """
        Validate a correction for quality
        
        Args:
            original: Original text
            corrected: Corrected text
            confidence: Model confidence
            
        Returns:
            (is_valid, reason)
        """
        # Check text length
        if len(corrected.strip()) < self.min_text_length:
            return False, "Text too short"
        
        if len(corrected) > self.max_text_length:
            return False, "Text too long"
        
        # Check confidence
        if confidence > 0.8:
            # High confidence corrections might be unnecessary
            if original == corrected:
                return False, "No change made"
        
        # Check if correction is meaningful
        if len(original) > 0 and len(corrected) > 0:
            similarity = self._calculate_similarity(original, corrected)
            if similarity > 0.95:
                return False, "Minimal change"
        
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
        # Check for excessive repetition
        if re.search(r'(.)\1{5,}', text):
            return True
        
        # Check for random characters
        if len(re.findall(r'[^a-zA-Z0-9\s\.,!?;:\'\"\-]', text)) > len(text) * 0.3:
            return True
        
        # Check for very long words (likely not real words)
        words = text.split()
        for word in words:
            if len(word) > 30:
                return True
        
        return False
    
    def filter_corrections(self, corrections: List[Dict]) -> List[Dict]:
        """
        Filter corrections by quality
        
        Args:
            corrections: List of correction dictionaries
            
        Returns:
            Filtered list of corrections
        """
        valid = []
        for correction in corrections:
            is_valid, reason = self.validate_correction(
                correction.get("original_text", ""),
                correction.get("corrected_text", ""),
                correction.get("confidence", 0.5)
            )
            
            if is_valid:
                valid.append(correction)
        
        return valid
    
    def remove_duplicates(self, corrections: List[Dict]) -> List[Dict]:
        """
        Remove duplicate corrections
        
        Args:
            corrections: List of correction dictionaries
            
        Returns:
            Deduplicated list
        """
        seen = {}
        unique = []
        
        for correction in corrections:
            key = (correction.get("audio_hash"), correction.get("corrected_text"))
            
            if key not in seen:
                seen[key] = 1
                unique.append(correction)
            elif seen[key] < self.max_duplicates:
                seen[key] += 1
                unique.append(correction)
        
        return unique