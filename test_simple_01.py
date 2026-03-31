#!/usr/bin/env python3
"""
Simple test to verify transcription works
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch
import librosa
import numpy as np

from src.core.transcriber import Transcriber

def test():
    print("=" * 50)
    print("Testing Transcriber")
    print("=" * 50)
    
    # Check CUDA
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    # Path to your custom model - UPDATE THIS!
    model_path = r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\whisper-tiny"
    
    # If custom model not found, use standard tiny model
    use_custom = Path(model_path).exists()
    
    if use_custom:
        print(f"Using custom model: {model_path}")
        transcriber = Transcriber(
            model_size="custom",
            device=device,
            compute_type="float32",
            language="en",
            custom_model_path=model_path
        )
    else:
        print("Using standard tiny model")
        transcriber = Transcriber(
            model_size="tiny",
            device=device,
            compute_type="float32",
            language="en"
        )
    
    # Load model
    print("\nLoading model...")
    if not transcriber.load_model():
        print("❌ Failed to load model")
        return
    
    print("✅ Model loaded")
    
    # Create test audio (2 seconds of beep)
    print("\nCreating test audio...")
    sr = 16000
    duration = 2
    t = np.linspace(0, duration, int(sr * duration))
    # Simple beep at 440 Hz
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    
    # Add some silence at start
    audio = np.concatenate([np.zeros(int(sr * 0.5)), audio])
    
    print(f"Audio shape: {audio.shape}, duration: {len(audio)/sr:.1f}s")
    
    # Transcribe
    print("\nTranscribing...")
    text = transcriber.transcribe_chunk(audio)
    
    print(f"\n📝 Result: '{text}'")
    
    if text and text.strip():
        print("✅ Transcription successful!")
    else:
        print("⚠️ No text generated")
        
        # Try with a real audio file if available
        test_file = Path(r"D:\work\whisper_transcriptor\test_audio.wav")
        if test_file.exists():
            print(f"\nTesting with real audio file: {test_file}")
            audio, sr = librosa.load(str(test_file), sr=16000)
            text = transcriber.transcribe_chunk(audio)
            print(f"Result: '{text}'")

if __name__ == "__main__":
    test()