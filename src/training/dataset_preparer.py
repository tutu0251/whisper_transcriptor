"""
Dataset Preparer Module
Prepare audio-text datasets for training
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple
import json


class DatasetPreparer:
    """Prepare datasets for Whisper fine-tuning"""
    
    def __init__(self):
        self.dataset = []
    
    def load_from_folder(self, folder_path: str) -> List[Dict]:
        """Load audio and text files from folder"""
        folder = Path(folder_path)
        audio_files = list(folder.glob("*.wav")) + list(folder.glob("*.mp3"))
        
        for audio_file in audio_files:
            text_file = audio_file.with_suffix(".txt")
            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                
                self.dataset.append({
                    "audio": str(audio_file),
                    "text": text
                })
        
        return self.dataset
    
    def split_dataset(self, train_ratio: float = 0.9) -> Tuple[List, List]:
        """Split dataset into train and validation"""
        split_idx = int(len(self.dataset) * train_ratio)
        return self.dataset[:split_idx], self.dataset[split_idx:]
    
    def validate_dataset(self) -> List[str]:
        """Validate dataset and return errors"""
        errors = []
        for i, item in enumerate(self.dataset):
            if not os.path.exists(item["audio"]):
                errors.append(f"Audio file not found: {item['audio']}")
            if not item["text"].strip():
                errors.append(f"Empty text for: {item['audio']}")
        return errors
    
    def export_json(self, file_path: str):
        """Export dataset as JSON"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.dataset, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict:
        """Get dataset statistics"""
        total_duration = 0
        total_words = 0
        
        for item in self.dataset:
            total_words += len(item["text"].split())
            # TODO: Get audio duration
            total_duration += 0
        
        return {
            "samples": len(self.dataset),
            "total_words": total_words,
            "total_duration_seconds": total_duration,
            "avg_duration": total_duration / len(self.dataset) if self.dataset else 0,
            "avg_words": total_words / len(self.dataset) if self.dataset else 0
        }
