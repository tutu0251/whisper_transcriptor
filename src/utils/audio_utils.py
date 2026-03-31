"""
Audio Utilities
Audio processing helper functions
"""

import numpy as np
from typing import Optional


def normalize_audio(audio_data: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """Normalize audio to target dB level"""
    rms = np.sqrt(np.mean(audio_data ** 2))
    if rms > 0:
        gain = 10 ** ((target_db - 20 * np.log10(rms)) / 20)
        return audio_data * gain
    return audio_data


def resample_audio(audio_data: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """Resample audio to target sample rate"""
    if original_rate == target_rate:
        return audio_data
    
    import scipy.signal
    duration = len(audio_data) / original_rate
    target_len = int(duration * target_rate)
    return scipy.signal.resample(audio_data, target_len)


def convert_to_mono(audio_data: np.ndarray) -> np.ndarray:
    """Convert stereo to mono by averaging channels"""
    if len(audio_data.shape) == 1:
        return audio_data
    
    return np.mean(audio_data, axis=1)


def trim_silence(audio_data: np.ndarray, sample_rate: int, 
                 silence_threshold: float = 0.01) -> np.ndarray:
    """Trim silence from beginning and end"""
    energy = np.abs(audio_data)
    non_silent = energy > silence_threshold
    
    # Find first and last non-silent samples
    start = np.argmax(non_silent)
    end = len(audio_data) - np.argmax(non_silent[::-1])
    
    return audio_data[start:end]
