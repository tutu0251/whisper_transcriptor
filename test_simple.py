# test_simple.py
import sys
sys.path.insert(0, r"D:\work\whisper_transcriptor\video_audio_transcriber")

from src.core.transcriber import Transcriber
import librosa
import numpy as np

# Initialize transcriber
transcriber = Transcriber(
    custom_model_path=r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\whisper-tiny",
    device="cuda",
    compute_type="float32",
    language="en"
)

# Load model
if transcriber.load_model():
    print("✅ Model loaded")
    
    # Create test audio (2 seconds of beep)
    sr = 16000
    t = np.linspace(0, 2, int(sr * 2))
    audio = 0.5 * np.sin(2 * np.pi * 440 * t)
    
    # Transcribe
    text = transcriber.transcribe_chunk(audio)
    print(f"📝 Transcription: '{text}'")
else:
    print("❌ Model failed to load")