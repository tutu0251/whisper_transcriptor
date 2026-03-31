"""
Playlist Widget Module
File queue management with drag-and-drop support
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QListWidgetItem, QFileDialog, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from pathlib import Path


class PlaylistWidget(QWidget):
    """Playlist widget for queue management"""
    
    # Signal emitted when a file is selected
    file_selected = pyqtSignal(str)
    playlist_changed = pyqtSignal(int)  # Number of files in playlist
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.setup_ui()
        self.setAcceptDrops(True)
    
    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Playlist list
        self.playlist = QListWidget()
        self.playlist.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.playlist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.playlist)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("📂 Add Files")
        self.add_btn.clicked.connect(self.add_files)
        btn_layout.addWidget(self.add_btn)
        
        self.add_folder_btn = QPushButton("📁 Add Folder")
        self.add_folder_btn.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.add_folder_btn)
        
        self.remove_btn = QPushButton("❌ Remove")
        self.remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.remove_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear All")
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
    
    def add_file(self, file_path: str):
        """
        Add a single file to playlist
        
        Args:
            file_path: Path to media file
        """
        file_name = Path(file_path).name
        item = QListWidgetItem(f"🎬 {file_name}")
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.playlist.addItem(item)
        self.playlist_changed.emit(self.playlist.count())
    
    def add_files(self):
        """Add files to playlist"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Media Files",
            "",
            "Media Files (*.mp4 *.avi *.mkv *.mov *.mp3 *.wav *.flac *.m4a);;All Files (*.*)"
        )
        
        for file_path in file_paths:
            self.add_file(file_path)
    
    def add_folder(self):
        """Add all media files from a folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Add Folder",
            ""
        )
        
        if folder_path:
            from src.utils.file_utils import get_media_files
            media_files = get_media_files(folder_path)
            
            for file_path in media_files:
                self.add_file(file_path)
    
    def remove_selected(self):
        """Remove selected items"""
        for item in self.playlist.selectedItems():
            row = self.playlist.row(item)
            self.playlist.takeItem(row)
        
        self.playlist_changed.emit(self.playlist.count())
    
    def clear_all(self):
        """Clear all items"""
        self.playlist.clear()
        self.playlist_changed.emit(0)
    
    def on_item_double_clicked(self, item):
        """Handle double-click on playlist item"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.current_file = file_path
            self.file_selected.emit(file_path)
    
    def show_context_menu(self, position):
        """Show context menu for playlist items"""
        item = self.playlist.itemAt(position)
        if item:
            menu = QMenu()
            
            play_action = menu.addAction("▶ Play")
            remove_action = menu.addAction("❌ Remove")
            menu.addSeparator()
            reveal_action = menu.addAction("📂 Reveal in Explorer")
            
            action = menu.exec(self.playlist.mapToGlobal(position))
            
            if action == play_action:
                self.on_item_double_clicked(item)
            elif action == remove_action:
                row = self.playlist.row(item)
                self.playlist.takeItem(row)
                self.playlist_changed.emit(self.playlist.count())
            elif action == reveal_action:
                import subprocess
                import os
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path:
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
    
    def get_files(self) -> list:
        """Get list of all files in playlist"""
        files = []
        for i in range(self.playlist.count()):
            item = self.playlist.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                files.append(file_path)
        return files
    
    def get_current_file(self) -> str:
        """Get currently selected file"""
        return self.current_file
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path:
                # Check if it's a file or folder
                import os
                if os.path.isfile(file_path):
                    self.add_file(file_path)
                elif os.path.isdir(file_path):
                    from src.utils.file_utils import get_media_files
                    media_files = get_media_files(file_path)
                    for media_file in media_files:
                        self.add_file(media_file)
        
        event.acceptProposedAction()