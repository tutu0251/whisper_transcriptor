#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Path to your custom model - UPDATE THIS!
model_path = r"D:\work\whisper_transcriptor\video_audio_transcriber\models_cache\custom\whisper"

print(f"Checking model at: {model_path}")

if not Path(model_path).exists():
    print(f"❌ Model path does not exist!")
    print("Please update the model_path variable")
    sys.exit(1)

# Check required files
required = ["config.json", "tokenizer_config.json", "model.safetensors"]
for f in required:
    file_path = Path(model_path) / f
    if file_path.exists():
        print(f"✅ Found: {f}")
    else:
        print(f"❌ Missing: {f}")

# Try to load model
try:
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    print("✅ transformers imported")
    
    print("Loading processor...")
    processor = WhisperProcessor.from_pretrained(str(model_path))
    print("✅ Processor loaded")
    
    print("Loading model...")
    model = WhisperForConditionalGeneration.from_pretrained(str(model_path))
    print("✅ Model loaded")
    
    print("✅ Model loading successful!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()