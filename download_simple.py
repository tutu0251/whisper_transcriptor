#!/usr/bin/env python3
"""
Simple script to download a single Whisper model for testing
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def download_tiny_model():
    """Download the tiny Whisper model using transformers"""
    try:
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        import torch

        print("Downloading openai/whisper-tiny...")

        # Download processor
        processor = WhisperProcessor.from_pretrained("openai/whisper-tiny")
        processor.save_pretrained("./models/whisper-tiny")

        # Download model
        model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-tiny")
        model.save_pretrained("./models/whisper-tiny")

        print("✅ Successfully downloaded whisper-tiny to ./models/whisper-tiny/")
        print("   Model files:", list(Path("./models/whisper-tiny").glob("*")))

        # Test loading
        print("Testing model loading...")
        test_processor = WhisperProcessor.from_pretrained("./models/whisper-tiny")
        test_model = WhisperForConditionalGeneration.from_pretrained("./models/whisper-tiny")
        print("✅ Model loads successfully!")

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install transformers: pip install transformers")
    except Exception as e:
        print(f"❌ Failed to download model: {e}")

if __name__ == "__main__":
    download_tiny_model()