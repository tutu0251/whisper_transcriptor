"""
File Utilities
File handling helper functions
"""

import os
from pathlib import Path
from typing import List, Set


def get_media_files(folder_path: str) -> List[str]:
    """Get all media files in folder"""
    extensions = {'.mp4', '.avi', '.mkv', '.mov', '.mp3', '.wav', '.flac', '.m4a'}
    folder = Path(folder_path)
    
    files = []
    for ext in extensions:
        files.extend(folder.glob(f"*{ext}"))
    
    return sorted([str(f) for f in files])


def find_srt_file(media_path: str) -> str:
    """Find associated SRT file for media"""
    media_path = Path(media_path)
    srt_path = media_path.with_suffix(".srt")
    
    if srt_path.exists():
        return str(srt_path)
    
    # Try with .vtt
    vtt_path = media_path.with_suffix(".vtt")
    if vtt_path.exists():
        return str(vtt_path)
    
    return None


def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    return os.path.getsize(file_path)


def format_file_size(size_bytes: int) -> str:
    """Format file size as human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
