"""
Model Manager Module
Download, cache, and manage local Whisper models (both standard and custom)
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ModelInfo:
    """Information about a model"""
    name: str
    type: str  # "standard" or "custom"
    size_mb: float
    path: str
    is_downloaded: bool
    is_active: bool = False
    language: str = "multilingual"


class ModelManager:
    """Manage local Whisper models (standard and custom)"""
    
    # Standard Whisper models with their sizes in MB
    STANDARD_MODELS = {
        "tiny": {"size_mb": 39, "url": "https://openaipublic.azureedge.net/main/whisper/models/tiny.pt"},
        "base": {"size_mb": 74, "url": "https://openaipublic.azureedge.net/main/whisper/models/base.pt"},
        "small": {"size_mb": 244, "url": "https://openaipublic.azureedge.net/main/whisper/models/small.pt"},
        "medium": {"size_mb": 769, "url": "https://openaipublic.azureedge.net/main/whisper/models/medium.pt"},
        "large": {"size_mb": 1540, "url": "https://openaipublic.azureedge.net/main/whisper/models/large-v2.pt"},
    }
    
    # Hugging Face Whisper models
    HF_WHISPER_MODELS = [
        "openai/whisper-tiny",
        "openai/whisper-base", 
        "openai/whisper-small",
        "openai/whisper-medium",
        "openai/whisper-large-v2",
        "openai/whisper-large-v3",
        "openai/whisper-tiny.en",
        "openai/whisper-base.en",
        "openai/whisper-small.en",
        "openai/whisper-medium.en",
    ]
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "whisper"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create custom models subdirectory
        self.custom_dir = self.cache_dir / "custom"
        self.custom_dir.mkdir(exist_ok=True)
        
        # Create Hugging Face models directory
        self.hf_dir = Path("./models")
        self.hf_dir.mkdir(exist_ok=True)
    
    def get_model_path(self, model_name: str) -> Path:
        """Get path to standard model file"""
        return self.cache_dir / f"{model_name}.pt"
    
    def get_hf_model_path(self, model_name: str) -> Path:
        """Get path to Hugging Face model folder"""
        return self.hf_dir / Path(model_name).name
    
    def get_custom_model_path(self, model_name: str) -> Path:
        """Get path to registered custom model folder"""
        return self.custom_dir / model_name
    
    def get_hf_model_id(self, model_name: str) -> Optional[str]:
        """Get the Hugging Face repo ID for a Whisper size"""
        if model_name == "large":
            return "openai/whisper-large-v2"
        return f"openai/whisper-{model_name}"
    
    def download_hf_model(self, model_name: str) -> bool:
        """Download a Hugging Face Whisper model into the local models folder."""
        model_id = self.get_hf_model_id(model_name)
        if not model_id:
            return False

        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("⚠️ huggingface_hub is not installed. Install it with: pip install huggingface-hub")
            return False

        output_dir = self.get_hf_model_path(model_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            snapshot_download(
                repo_id=model_id,
                local_dir=output_dir,
                local_dir_use_symlinks=False,
                resume_download=True
            )
            return True
        except Exception as e:
            print(f"Error downloading HF model {model_id}: {e}")
            return False

    def is_hf_model_available(self, model_name: str) -> bool:
        """Check if Hugging Face model is available"""
        model_path = self.get_hf_model_path(model_name)
        required_files = ["config.json", "model.safetensors", "tokenizer_config.json"]
        
        if not model_path.exists():
            return False
        
        # Check required files
        for file in required_files:
            if not (model_path / file).exists():
                return False
        
        return True
    
    def get_model_size_mb(self, model_name: str) -> float:
        """Get size of standard model in MB"""
        if model_name in self.STANDARD_MODELS:
            return self.STANDARD_MODELS[model_name]["size_mb"]
        return 0.0
    
    def is_model_downloaded(self, model_name: str) -> bool:
        """Check if standard model is downloaded"""
        return self.get_model_path(model_name).exists()
    
    def is_custom_model_available(self, model_name: str) -> bool:
        """Check if custom model is available"""
        model_path = self.get_custom_model_path(model_name)
        required_files = ["config.json", "model.safetensors", "tokenizer_config.json"]
        
        if not model_path.exists():
            return False
        
        # Check required files
        for file in required_files:
            if not (model_path / file).exists():
                return False
        
        return True
    
    def register_custom_model(self, model_path: str, model_name: str = None) -> str:
        """
        Register a custom model by copying it to the cache
        
        Args:
            model_path: Path to custom model folder
            model_name: Name for the model (auto-generated if None)
            
        Returns:
            Name of registered model
        """
        source = Path(model_path)
        
        if not source.exists():
            raise FileNotFoundError(f"Model path not found: {model_path}")
        
        # Generate name if not provided
        if model_name is None:
            model_name = source.name
            if model_name == "":
                import time
                model_name = f"custom_{int(time.time())}"
        
        # Destination path
        dest = self.get_custom_model_path(model_name)
        
        # Copy model files
        if dest.exists():
            shutil.rmtree(dest)
        
        shutil.copytree(source, dest)
        
        return model_name
    
    def list_models(self) -> List[ModelInfo]:
        """List all available models (standard and custom)"""
        models = []
        
        # Standard models
        for name, info in self.STANDARD_MODELS.items():
            models.append(ModelInfo(
                name=name,
                type="standard",
                size_mb=info["size_mb"],
                path=str(self.get_model_path(name)),
                is_downloaded=self.is_model_downloaded(name)
            ))
        
        # Custom models
        for model_dir in self.custom_dir.iterdir():
            if model_dir.is_dir():
                # Calculate size
                total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                size_mb = total_size / (1024 * 1024)
                
                models.append(ModelInfo(
                    name=model_dir.name,
                    type="custom",
                    size_mb=size_mb,
                    path=str(model_dir),
                    is_downloaded=True
                ))
        
        # Hugging Face models
        for model_id in self.HF_WHISPER_MODELS:
            model_name = model_id.split("/")[-1]  # Extract model name
            model_path = self.get_hf_model_path(model_id)
            is_downloaded = self.is_hf_model_available(model_id)
            
            # Estimate size based on model name
            size_mb = self._estimate_hf_model_size(model_name)
            
            models.append(ModelInfo(
                name=model_name,
                type="huggingface",
                size_mb=size_mb,
                path=str(model_path),
                is_downloaded=is_downloaded
            ))
        
        return models
    
    def _estimate_hf_model_size(self, model_name: str) -> float:
        """Estimate Hugging Face model size based on name"""
        size_map = {
            "tiny": 150,
            "base": 290,
            "small": 950,
            "medium": 3000,
            "large": 6000,
        }
        
        for size_name, size_mb in size_map.items():
            if size_name in model_name.lower():
                return size_mb
        
        return 1000  # Default estimate
    
    def delete_model(self, model_name: str) -> bool:
        """
        Delete a model
        
        Args:
            model_name: Name of model to delete
            
        Returns:
            True if successful
        """
        # Check standard models
        if model_name in self.STANDARD_MODELS:
            model_path = self.get_model_path(model_name)
            if model_path.exists():
                try:
                    model_path.unlink()
                    return True
                except Exception:
                    return False
        
        # Check custom models
        custom_path = self.get_custom_model_path(model_name)
        if custom_path.exists():
            try:
                shutil.rmtree(custom_path)
                return True
            except Exception:
                return False
        
        return False
    
    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get information about a specific model"""
        # Check standard
        if model_name in self.STANDARD_MODELS:
            return {
                "name": model_name,
                "type": "standard",
                "size_mb": self.STANDARD_MODELS[model_name]["size_mb"],
                "path": str(self.get_model_path(model_name)),
                "downloaded": self.is_model_downloaded(model_name)
            }
        
        # Check custom
        custom_path = self.get_custom_model_path(model_name)
        if custom_path.exists():
            total_size = sum(f.stat().st_size for f in custom_path.rglob("*") if f.is_file())
            return {
                "name": model_name,
                "type": "custom",
                "size_mb": total_size / (1024 * 1024),
                "path": str(custom_path),
                "downloaded": True
            }
        
        return None
    
    def download_model(self, model_name: str, progress_callback=None) -> bool:
        """
        Download a standard Whisper model
        
        Args:
            model_name: Name of model to download
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful
        """
        import requests
        
        if model_name not in self.STANDARD_MODELS:
            return False
        
        if self.is_model_downloaded(model_name):
            return True
        
        url = self.STANDARD_MODELS[model_name]["url"]
        model_path = self.get_model_path(model_name)
        temp_path = model_path.with_suffix(".tmp")
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            temp_path.rename(model_path)
            return True
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            print(f"Error downloading model: {e}")
            return False
    
    def get_cache_size(self) -> int:
        """Get total cache size in bytes"""
        total = 0
        
        # Standard models
        for model_name in self.STANDARD_MODELS:
            model_path = self.get_model_path(model_name)
            if model_path.exists():
                total += model_path.stat().st_size
        
        # Custom models
        for model_dir in self.custom_dir.iterdir():
            if model_dir.is_dir():
                total += sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
        
        return total
    
    def clear_cache(self) -> int:
        """Delete all models"""
        deleted = 0
        
        # Delete standard models
        for model_name in self.STANDARD_MODELS:
            if self.delete_model(model_name):
                deleted += 1
        
        # Delete custom models
        for model_dir in self.custom_dir.iterdir():
            if model_dir.is_dir():
                try:
                    shutil.rmtree(model_dir)
                    deleted += 1
                except Exception:
                    pass
        
        return deleted
    
    def get_model_download_status(self) -> Dict[str, bool]:
        """Get download status of all standard models"""
        status = {}
        for model_name in self.STANDARD_MODELS:
            status[model_name] = self.is_model_downloaded(model_name)
        return status