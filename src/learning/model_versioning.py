"""
Model Versioning Module
Manage model versions, version comparison, and rollback functionality
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ModelVersion:
    """Model version metadata"""
    version: str
    created_at: str
    base_model: str
    corrections_trained: int
    file_path: str
    file_size_mb: float
    is_active: bool
    wer_score: float
    training_session_id: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelVersion':
        """Create from dictionary"""
        return cls(**data)


class ModelVersioning:
    """Manage model versions and version history"""
    
    def __init__(self, models_dir: str = None):
        """
        Initialize model version manager
        
        Args:
            models_dir: Directory to store model versions
        """
        if models_dir is None:
            models_dir = Path.home() / ".transcriber" / "models"
        
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.models_dir / "versions.json"
        self.versions: List[ModelVersion] = []
        
        self.load_metadata()
    
    def load_metadata(self):
        """Load version metadata from file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.versions = [ModelVersion.from_dict(v) for v in data]
            except Exception as e:
                print(f"Error loading metadata: {e}")
                self.versions = []
    
    def save_metadata(self):
        """Save version metadata to file"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump([v.to_dict() for v in self.versions], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def add_version(self, model: ModelVersion) -> bool:
        """
        Add a new model version
        
        Args:
            model: ModelVersion instance
            
        Returns:
            True if successful
        """
        # Check if version already exists
        existing = self.get_version(model.version)
        if existing:
            return False
        
        self.versions.append(model)
        self.save_metadata()
        return True
    
    def get_version(self, version: str) -> Optional[ModelVersion]:
        """Get a specific version by name"""
        for v in self.versions:
            if v.version == version:
                return v
        return None
    
    def get_all_versions(self) -> List[ModelVersion]:
        """Get all versions sorted by creation date"""
        return sorted(self.versions, key=lambda x: x.created_at, reverse=True)
    
    def get_active_version(self) -> Optional[ModelVersion]:
        """Get the currently active model version"""
        for v in self.versions:
            if v.is_active:
                return v
        return None
    
    def set_active_version(self, version: str) -> bool:
        """
        Set a specific version as active
        
        Args:
            version: Version string to activate
            
        Returns:
            True if successful
        """
        found = False
        for v in self.versions:
            if v.version == version:
                v.is_active = True
                found = True
            else:
                v.is_active = False
        
        if found:
            self.save_metadata()
        
        return found
    
    def delete_version(self, version: str) -> bool:
        """
        Delete a model version
        
        Args:
            version: Version string to delete
            
        Returns:
            True if successful
        """
        for i, v in enumerate(self.versions):
            if v.version == version:
                # Don't delete active version
                if v.is_active:
                    return False
                
                # Delete model file
                model_path = Path(v.file_path)
                if model_path.exists():
                    try:
                        model_path.unlink()
                    except Exception:
                        pass
                
                # Remove from list
                del self.versions[i]
                self.save_metadata()
                return True
        
        return False
    
    def rollback(self, version: str = None) -> Optional[ModelVersion]:
        """
        Rollback to a previous version
        
        Args:
            version: Version to rollback to (if None, rollback to previous)
            
        Returns:
            The activated version or None
        """
        if version:
            if self.set_active_version(version):
                return self.get_version(version)
            return None
        
        # Rollback to previous version (the one before active)
        active = self.get_active_version()
        if not active:
            return None
        
        all_versions = self.get_all_versions()
        for i, v in enumerate(all_versions):
            if v.version == active.version and i + 1 < len(all_versions):
                previous = all_versions[i + 1]
                self.set_active_version(previous.version)
                return previous
        
        return None
    
    def get_version_history(self, limit: int = 10) -> List[Dict]:
        """
        Get version history with statistics
        
        Args:
            limit: Maximum number of versions to return
            
        Returns:
            List of version info dictionaries
        """
        versions = self.get_all_versions()[:limit]
        
        history = []
        for v in versions:
            history.append({
                "version": v.version,
                "created_at": v.created_at,
                "base_model": v.base_model,
                "corrections": v.corrections_trained,
                "wer_score": v.wer_score,
                "size_mb": v.file_size_mb,
                "is_active": v.is_active
            })
        
        return history
    
    def get_improvement_trend(self) -> List[Tuple[str, float]]:
        """
        Get WER improvement trend over versions
        
        Returns:
            List of (version, wer_score) tuples
        """
        versions = self.get_all_versions()
        return [(v.version, v.wer_score) for v in versions if v.wer_score > 0]
    
    def cleanup_old_versions(self, keep_count: int = 5) -> int:
        """
        Delete old versions, keeping only the most recent
        
        Args:
            keep_count: Number of recent versions to keep
            
        Returns:
            Number of versions deleted
        """
        versions = self.get_all_versions()
        
        if len(versions) <= keep_count:
            return 0
        
        deleted = 0
        for v in versions[keep_count:]:
            if not v.is_active:
                if self.delete_version(v.version):
                    deleted += 1
        
        return deleted
    
    def export_version(self, version: str, export_path: str) -> bool:
        """
        Export a model version to a file
        
        Args:
            version: Version to export
            export_path: Path to export to
            
        Returns:
            True if successful
        """
        v = self.get_version(version)
        if not v:
            return False
        
        source_path = Path(v.file_path)
        if not source_path.exists():
            return False
        
        try:
            shutil.copy2(source_path, export_path)
            return True
        except Exception:
            return False
    
    def import_version(self, file_path: str, version: str = None) -> Optional[ModelVersion]:
        """
        Import a model version from a file
        
        Args:
            file_path: Path to model file
            version: Version string (auto-generated if None)
            
        Returns:
            The imported ModelVersion or None
        """
        source = Path(file_path)
        if not source.exists():
            return None
        
        # Generate version name if not provided
        if version is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            version = f"imported_{timestamp}"
        
        # Destination path
        dest = self.models_dir / f"{version}.pt"
        
        try:
            shutil.copy2(source, dest)
            
            # Create metadata
            model_version = ModelVersion(
                version=version,
                created_at=datetime.now().isoformat(),
                base_model="imported",
                corrections_trained=0,
                file_path=str(dest),
                file_size_mb=dest.stat().st_size / (1024 * 1024),
                is_active=False,
                wer_score=0.0,
                training_session_id=0
            )
            
            self.add_version(model_version)
            return model_version
            
        except Exception as e:
            print(f"Error importing version: {e}")
            return None
    
    def compare_versions(self, version1: str, version2: str) -> Dict:
        """
        Compare two model versions
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            Comparison dictionary
        """
        v1 = self.get_version(version1)
        v2 = self.get_version(version2)
        
        if not v1 or not v2:
            return {"error": "Version not found"}
        
        wer_improvement = v2.wer_score - v1.wer_score if v1.wer_score > 0 and v2.wer_score > 0 else 0
        size_diff = v2.file_size_mb - v1.file_size_mb
        
        return {
            "version1": version1,
            "version2": version2,
            "wer_improvement": wer_improvement,
            "size_diff_mb": size_diff,
            "corrections_diff": v2.corrections_trained - v1.corrections_trained,
            "better_version": version2 if wer_improvement < 0 else version1
        }
    
    def get_stats(self) -> Dict:
        """
        Get version statistics
        
        Returns:
            Statistics dictionary
        """
        versions = self.get_all_versions()
        active = self.get_active_version()
        
        return {
            "total_versions": len(versions),
            "active_version": active.version if active else None,
            "total_size_mb": sum(v.file_size_mb for v in versions),
            "oldest_version": versions[-1].version if versions else None,
            "newest_version": versions[0].version if versions else None,
            "best_wer": min((v.wer_score for v in versions if v.wer_score > 0), default=0),
            "total_corrections": sum(v.corrections_trained for v in versions)
        }