"""
Learning Tabs Module
Contains UI components for continuous learning and model improvement tracking.
"""

from src.gui.learning_tabs.learning_settings import LearningSettings
from src.gui.learning_tabs.improvement_dashboard import ImprovementDashboard
from src.gui.learning_tabs.version_manager import VersionManager

__all__ = [
    "LearningSettings",
    "ImprovementDashboard",
    "VersionManager",
]