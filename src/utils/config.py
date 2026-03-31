"""
Configuration Manager
Load and save application settings
"""

import json
from pathlib import Path
from typing import Any, Dict


class Config:
    """Application configuration manager"""
    
    DEFAULT_CONFIG = {
        "language": "auto",
        "model_size": "small",
        "chunk_duration": 2.5,
        "chunk_overlap": 0.5,
        "device": "auto",
        "compute_type": "fp16",
        "theme": "dark",
        "font_size": 11,
        "font_family": "Monospace",
        "auto_export": True,
        "auto_save_interval": 5,
        "last_directory": "",
        "export_directory": "./output",
        "model_cache": "./models_cache",
    }
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            home = Path.home()
            app_data = home / ".transcriber"
            app_data.mkdir(exist_ok=True)
            config_path = app_data / "config.json"
        
        self.config_path = Path(config_path)
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
    
    def reset(self):
        """Reset to default configuration"""
        self.config = self.DEFAULT_CONFIG.copy()
