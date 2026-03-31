"""
Test script for custom Whisper model - Fixed dtype issue
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

import torch
import librosa
import numpy as np
from transformers import WhisperProcessor, WhisperForConditionalGeneration


def test_custom_model():
    print("=" * 60)
    print("Testing Custom Whisper Model")
    print("=" * 60)
    
    # Path to your custom model - UPDATE THIS!
    model_path = r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\custom\whisper"
    
    # Alternative paths to try
    possible_paths = [
        r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\custom\whisper",
        r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\whisper-tiny",
        r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\custom",
        r"D:\work\whisper_transcriptor\video_audio_transcriber\models\whisper-tiny",
    ]
    
    # Find the correct path
    found_path = None
    for path in possible_paths:
        p = Path(path)
        if p.exists() and (p / "config.json").exists():
            found_path = p
            model_path = str(p)
            break
    
    if not found_path:
        print("❌ Model not found. Please update the model_path variable.")
        print("\nSearch locations:")
        for path in possible_paths:
            print(f"  - {path}")
        
        # List what's in the custom directory
        custom_dir = Path(r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\custom")
        if custom_dir.exists():
            print("\n📁 Contents of models_cache/custom:")
            for item in custom_dir.iterdir():
                if item.is_dir():
                    print(f"   📂 {item.name}")
                else:
                    print(f"   📄 {item.name}")
        return
    
    print(f"📁 Model path: {model_path}")
    
    # Check CUDA
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🔧 Device: {device}")
    
    if device == "cuda":
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    try:
        print("\n📥 Loading processor...")
        processor = WhisperProcessor.from_pretrained(model_path)
        print("✅ Processor loaded")
        
        print("\n📥 Loading model...")
        # CRITICAL FIX: Load model with float32, then convert after moving to device
        model = WhisperForConditionalGeneration.from_pretrained(
            model_path,
            torch_dtype=torch.float32,  # Load in float32 first
            low_cpu_mem_usage=True
        )
        
        print(f"   Model dtype before moving: {model.dtype}")
        
        # Move to device and convert dtype
        if device == "cuda":
            print("   Converting to float16 for GPU...")
            model = model.half()  # Convert to half precision for GPU
            model.to(device)
        else:
            model.to(device)
        
        model.eval()
        print(f"   Model dtype after: {next(model.parameters()).dtype}")
        print("✅ Model loaded")
        
        # Create a proper test audio
        print("\n🎵 Creating test audio...")
        sample_rate = 16000
        duration = 3
        t = np.linspace(0, duration, int(sample_rate * duration))
        # Create a simple sine wave (440 Hz) with some silence at start
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        # Add a simple pattern to make it more "speech-like"
        envelope = np.exp(-t)
        audio = audio * envelope
        
        print(f"   Audio shape: {audio.shape}, sample rate: {sample_rate}")
        
        # Process audio - ensure input is float32
        audio_float32 = audio.astype(np.float32)
        
        input_features = processor(
            audio_float32, 
            sampling_rate=sample_rate, 
            return_tensors="pt"
        ).input_features
        
        print(f"   Input features dtype: {input_features.dtype}")
        
        # CRITICAL FIX: Convert input features to match model dtype
        model_dtype = next(model.parameters()).dtype
        input_features = input_features.to(dtype=model_dtype)
        input_features = input_features.to(device)
        
        print(f"   Input features after conversion: {input_features.dtype}")
        
        # Generate
        print("\n🎤 Generating transcription...")
        with torch.no_grad():
            predicted_ids = model.generate(
                input_features,
                language="en",
                task="transcribe",
                max_length=448,
                num_beams=3,
                early_stopping=True
            )
        
        # Decode
        transcription = processor.batch_decode(
            predicted_ids, 
            skip_special_tokens=True
        )[0]
        
        print(f"\n📝 Transcription: '{transcription}'")
        
        if transcription.strip():
            print("✅ Transcription successful!")
        else:
            print("⚠️ No text generated - model might need proper audio input")
            
        # Test with a real audio file if available
        test_audio = Path(r"D:\work\whisper_transcriptor\test_audio.wav")
        if test_audio.exists():
            print(f"\n🎵 Testing with real audio file: {test_audio.name}")
            audio, sr = librosa.load(str(test_audio), sr=16000)
            audio = audio.astype(np.float32)
            
            input_features = processor(
                audio, 
                sampling_rate=sr, 
                return_tensors="pt"
            ).input_features
            input_features = input_features.to(dtype=model_dtype).to(device)
            
            with torch.no_grad():
                predicted_ids = model.generate(
                    input_features,
                    language="en",
                    task="transcribe",
                    max_length=448
                )
            
            transcription = processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            print(f"📝 Real audio transcription: '{transcription}'")
        
        print("\n" + "=" * 60)
        print("Test complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_custom_model()