"""
GUI Module
Contains all user interface components for the application.
"""

try:
    from src.gui.main_window import MainWindow
except Exception:
    MainWindow = None

try:
    from src.gui.player_widget import PlayerWidget
except Exception:
    PlayerWidget = None

from src.gui.transcription_panel import TranscriptionPanel
from src.gui.srt_editor import SRTEditor
from src.gui.settings_dialog import SettingsDialog
from src.gui.model_manager_dialog import ModelManagerDialog
from src.gui.playlist_widget import PlaylistWidget
from src.gui.status_bar import StatusBar

__all__ = [
    "TranscriptionPanel",
    "SRTEditor",
    "SettingsDialog",
    "ModelManagerDialog",
    "PlaylistWidget",
    "StatusBar",
]

if MainWindow is not None:
    __all__.insert(0, "MainWindow")
if PlayerWidget is not None:
    __all__.insert(1, "PlayerWidget")