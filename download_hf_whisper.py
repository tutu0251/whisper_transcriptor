#!/usr/bin/env python3
"""
Download all available Hugging Face Whisper models
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def get_whisper_models():
    """Get all available Whisper models from Hugging Face"""
    # Use hardcoded list of known Whisper models since API search is complex
    models = [
        "openai/whisper-tiny",
        "openai/whisper-base",
        "openai/whisper-small",
        "openai/whisper-medium",
        "openai/whisper-large-v2",
        "openai/whisper-large-v3",
    ]

    return models

def download_model(model_id, output_dir):
    """Download a single model"""
    try:
        print(f"Downloading {model_id}...")
        snapshot_download(
            repo_id=model_id,
            local_dir=output_dir / model_id.split('/')[-1],
            local_dir_use_symlinks=False
        )
        print(f"✅ Downloaded {model_id}")
        return True
    except Exception as e:
        print(f"❌ Failed to download {model_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download Hugging Face Whisper models")
    parser.add_argument("--output-dir", "-o", default="./models",
                       help="Output directory for models")
    parser.add_argument("--models", "-m", nargs="+",
                       help="Specific models to download (default: all)")
    parser.add_argument("--list-only", "-l", action="store_true",
                       help="Only list available models")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("🔍 Finding available Whisper models...")
    models = get_whisper_models()

    if args.list_only:
        print(f"\n📋 Available Whisper models ({len(models)}):")
        for model in models:
            print(f"  - {model}")
        return

    if args.models:
        models = args.models

    print(f"\n📥 Downloading {len(models)} Whisper models to {output_dir}")
    print("=" * 60)

    successful = 0
    failed = 0

    for model_id in models:
        if download_model(model_id, output_dir):
            successful += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 Download Summary:")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📁 Models saved to: {output_dir.absolute()}")

if __name__ == "__main__":
    main()