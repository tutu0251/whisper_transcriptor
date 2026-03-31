"""
Training Tabs Module
Contains UI components for model training and fine-tuning.
"""

from src.gui.training_tabs.dataset_tab import DatasetTab
from src.gui.training_tabs.config_tab import ConfigTab
from src.gui.training_tabs.monitor_tab import MonitorTab

__all__ = [
    "DatasetTab",
    "ConfigTab",
    "MonitorTab",
]