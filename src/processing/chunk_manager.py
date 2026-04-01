"""
Chunk Manager Module with sentence-aware chunking
"""

import numpy as np
from typing import List, Dict, Tuple


class ChunkManager:
    """Manages audio chunking with sentence awareness"""
    
    def __init__(self, chunk_duration: float = 3.0, overlap: float = 0.5):
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.chunks = []
        
        # Sentence detection
        self.sentence_buffer = ""
        self.sentence_start = 0
        self.pending_chunks = []
    
    def split_audio_with_sentences(self, audio_data: np.ndarray, sample_rate: int,
                                    transcriber) -> List[Dict]:
        """
        Split audio and transcribe with sentence boundaries
        
        Args:
            audio_data: Full audio array
            sample_rate: Sample rate
            transcriber: Transcriber instance
            
        Returns:
            List of sentence chunks with text, start, end, confidence
        """
        print(f"🎤 Processing audio with sentence detection...")
        print(f"   Duration: {len(audio_data)/sample_rate:.1f} seconds")
        
        chunk_samples = int(self.chunk_duration * sample_rate)
        overlap_samples = int(self.overlap * sample_rate)
        step_samples = chunk_samples - overlap_samples
        
        sentences = []
        buffer = []
        
        for start in range(0, len(audio_data), step_samples):
            end = min(start + chunk_samples, len(audio_data))
            chunk = audio_data[start:end]
            
            # Transcribe chunk with word timestamps
            try:
                result = transcriber.transcribe_with_sentences(chunk)
                
                for item in result:
                    # Adjust timestamps to absolute time
                    item["start"] += start / sample_rate
                    item["end"] += start / sample_rate
                    buffer.append(item)
                    
                    # When we detect a sentence end, combine buffer
                    if item["is_sentence_end"]:
                        sentence_text = " ".join([b["text"] for b in buffer])
                        sentence_start = buffer[0]["start"]
                        sentence_end = buffer[-1]["end"]
                        avg_confidence = sum(b.get("confidence", 0.85) for b in buffer) / len(buffer)
                        
                        sentences.append({
                            "text": sentence_text.strip(),
                            "start": sentence_start,
                            "end": sentence_end,
                            "confidence": avg_confidence
                        })
                        buffer = []
                        
            except Exception as e:
                print(f"⚠️ Error processing chunk: {e}")
                continue
            
            if end == len(audio_data):
                break
        
        # Add any remaining text as a sentence
        if buffer:
            sentence_text = " ".join([b["text"] for b in buffer])
            sentence_start = buffer[0]["start"]
            sentence_end = buffer[-1]["end"]
            avg_confidence = sum(b.get("confidence", 0.85) for b in buffer) / len(buffer)
            
            sentences.append({
                "text": sentence_text.strip(),
                "start": sentence_start,
                "end": sentence_end,
                "confidence": avg_confidence
            })
        
        print(f"✅ Found {len(sentences)} sentences")
        return sentences
    
    def split_audio(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict]:
        """Original chunk splitting method (no sentence detection)"""
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