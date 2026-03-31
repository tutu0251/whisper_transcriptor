"""
Media Player Module
Handles video/audio playback using python-vlc
"""

import vlc
import os
from typing import Optional, Callable
from pathlib import Path


class MediaPlayer:
    """Media player wrapper for video/audio playback"""
    
    def __init__(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.current_media = None
        self.current_path = None
        self.is_playing = False
        self.position_callbacks = []
        self.end_callbacks = []
    
    def load_file(self, file_path: str) -> bool:
        """Load a media file for playback"""
        if not os.path.exists(file_path):
            return False
        
        self.current_path = file_path
        media = self.instance.media_new(file_path)
        self.player.set_media(media)
        self.current_media = media
        return True
    
    def play(self):
        """Start playback"""
        self.player.play()
        self.is_playing = True
    
    def pause(self):
        """Pause playback"""
        self.player.pause()
        self.is_playing = False
    
    def stop(self):
        """Stop playback"""
        self.player.stop()
        self.is_playing = False
    
    def set_position(self, position: float):
        """Set playback position (0.0 to 1.0)"""
        self.player.set_position(position)
    
    def get_position(self) -> float:
        """Get current playback position (0.0 to 1.0)"""
        return self.player.get_position()
    
    def get_time(self) -> int:
        """Get current time in milliseconds"""
        return self.player.get_time()
    
    def set_time(self, time_ms: int):
        """Set current time in milliseconds"""
        self.player.set_time(time_ms)
    
    def get_length(self) -> int:
        """Get media duration in milliseconds"""
        return self.player.get_length()
    
    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        self.player.audio_set_volume(volume)
    
    def get_volume(self) -> int:
        """Get current volume (0-100)"""
        return self.player.audio_get_volume()
    
    def set_rate(self, rate: float):
        """Set playback rate (0.5 to 2.0)"""
        self.player.set_rate(rate)
    
    def get_rate(self) -> float:
        """Get current playback rate"""
        return self.player.get_rate()
    
    def is_seekable(self) -> bool:
        """Check if media is seekable"""
        return self.player.is_seekable()
    
    def on_position_change(self, callback: Callable):
        """Register callback for position changes"""
        self.position_callbacks.append(callback)
    
    def on_media_end(self, callback: Callable):
        """Register callback for media end"""
        self.end_callbacks.append(callback)
    
    def update(self):
        """Update callbacks (call in main loop)"""
        if self.is_playing:
            for callback in self.position_callbacks:
                callback(self.get_position())
        
        if self.is_playing and self.player.get_state() == vlc.State.Ended:
            self.is_playing = False
            for callback in self.end_callbacks:
                callback()
    
    def get_video_output(self):
        """Get video output for embedding in GUI"""
        return None
