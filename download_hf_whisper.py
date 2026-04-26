#!/usr/bin/env python3
"""
Download Whisper models from Hugging Face.

By default, this script downloads only the model files that this project
actually needs, avoiding large optional TensorFlow and Flax artifacts.
"""

import argparse
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.model_manager import ModelManager


def get_whisper_models():
    """Get supported Whisper models for this project."""
    return [
        "openai/whisper-tiny",
        "openai/whisper-base",
        "openai/whisper-small",
        "openai/whisper-medium",
        "openai/whisper-large-v2",
        "openai/whisper-large-v3",
    ]


def download_model(model_id: str, output_dir: Path, essential_only: bool = True) -> bool:
    """Download a single model folder."""
    target_dir = output_dir / model_id.split("/")[-1]
    target_dir.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "repo_id": model_id,
        "local_dir": target_dir,
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }

    if essential_only:
        kwargs["allow_patterns"] = ModelManager.HF_ESSENTIAL_ALLOW_PATTERNS

    try:
        mode_text = "essential files" if essential_only else "full repo"
        print(f"Downloading {model_id} ({mode_text})...")
        snapshot_download(**kwargs)
        print(f"OK Downloaded {model_id} to {target_dir}")
        return True
    except Exception as e:
        print(f"ERROR Failed to download {model_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Hugging Face Whisper models for this project"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./models",
        help="Output directory for models",
    )
    parser.add_argument(
        "--models",
        "-m",
        nargs="+",
        help="Specific models to download (default: project-supported list)",
    )
    parser.add_argument(
        "--list-only",
        "-l",
        action="store_true",
        help="Only list available models",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Download full repositories instead of only essential files",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    models = get_whisper_models()

    if args.list_only:
        print(f"Available Whisper models ({len(models)}):")
        for model in models:
            print(f"  - {model}")
        return

    if args.models:
        models = args.models

    essential_only = not args.full
    mode_text = "essential files only" if essential_only else "full repositories"

    print(f"Downloading {len(models)} Whisper model(s) to {output_dir}")
    print(f"Mode: {mode_text}")
    print("=" * 60)

    successful = 0
    failed = 0

    for model_id in models:
        if download_model(model_id, output_dir, essential_only=essential_only):
            successful += 1
        else:
            failed += 1

    print("=" * 60)
    print("Download Summary:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Output: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
