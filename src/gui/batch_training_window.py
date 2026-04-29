"""
Batch training window.

This is a real workflow shell for scanning paired media/subtitle folders and
previewing a normalized dataset before wiring full training execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.subtitle_format_adapters import SubtitleFormatRegistry


class BatchTrainingWindow(QDialog):
    """Scan paired media/subtitle folders for fine-tuning input."""

    MEDIA_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".mp4", ".mkv", ".avi", ".mov"}

    def __init__(self, model_names: List[str], background_trainer=None, transcriber=None, parent=None):
        super().__init__(parent)
        self.model_names = model_names or ["small"]
        self.background_trainer = background_trainer
        self.transcriber = transcriber
        self.valid_pairs: List[Tuple[Path, Path]] = []
        self.issues: List[str] = []
        self.dataset_entries: List[Dict] = []
        self.detected_languages: set[str] = set()
        self.last_dataset_manifest: Optional[Path] = None
        self.setWindowTitle("Batch Training")
        self.resize(980, 720)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            "Batch Training From Paired Media + Subtitle Folders\n"
            "Scan a folder, validate media/subtitle pairs, and preview normalized subtitle data."
        )
        header.setStyleSheet(
            "QLabel { background: #1b2534; color: #eef4ff; border: 1px solid #41516b; border-radius: 10px; padding: 16px; font-size: 14px; }"
        )
        layout.addWidget(header)

        controls = QGroupBox("Batch Training Setup")
        form = QFormLayout(controls)
        self.folder_input = QLineEdit()
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.model_names)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Auto", "CPU", "CUDA"])
        self.subtitle_formats_combo = QComboBox()
        self.subtitle_formats_combo.addItems(["All supported formats", "SRT + SMI priority", "SRT only", "SMI only"])
        self.run_mode_combo = QComboBox()
        self.run_mode_combo.addItems(["Foreground", "Background"])
        form.addRow("Training folder", self.folder_input)
        form.addRow("Subtitle formats", self.subtitle_formats_combo)
        form.addRow("Model to train", self.model_combo)
        form.addRow("Device", self.device_combo)
        form.addRow("Training mode", self.run_mode_combo)
        layout.addWidget(controls)

        action_bar = QHBoxLayout()
        self.select_folder_btn = QPushButton("Select Folder")
        self.scan_btn = QPushButton("Scan Pairs")
        self.preview_btn = QPushButton("Preview Dataset")
        self.validate_btn = QPushButton("Validate Files")
        self.start_btn = QPushButton("Start Batch Training")
        for button in (self.select_folder_btn, self.scan_btn, self.preview_btn, self.validate_btn, self.start_btn):
            action_bar.addWidget(button)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        content = QHBoxLayout()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        valid_box = QGroupBox("Valid Pairs")
        valid_layout = QVBoxLayout(valid_box)
        self.valid_list = QListWidget()
        valid_layout.addWidget(self.valid_list)
        left_layout.addWidget(valid_box)

        issues_box = QGroupBox("Issues Found")
        issues_layout = QVBoxLayout(issues_box)
        self.issues_list = QListWidget()
        issues_layout.addWidget(self.issues_list)
        left_layout.addWidget(issues_box)
        content.addWidget(left, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        summary_box = QGroupBox("Dataset Summary")
        summary_form = QFormLayout(summary_box)
        self.valid_pairs_label = QLabel("0")
        self.issue_count_label = QLabel("0")
        self.estimated_segments_label = QLabel("0")
        self.estimated_duration_label = QLabel("00:00")
        self.detected_languages_label = QLabel("--")
        self.execution_mode_label = QLabel("--")
        summary_form.addRow("Valid pairs", self.valid_pairs_label)
        summary_form.addRow("Issues", self.issue_count_label)
        summary_form.addRow("Subtitle segments", self.estimated_segments_label)
        summary_form.addRow("Estimated duration", self.estimated_duration_label)
        summary_form.addRow("Detected languages", self.detected_languages_label)
        summary_form.addRow("Execution mode", self.execution_mode_label)
        right_layout.addWidget(summary_box)

        preview_box = QGroupBox("Training Preview")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        right_layout.addWidget(preview_box, 1)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(120)
        right_layout.addWidget(self._grouped_status_widget(), 0)
        content.addWidget(right, 1)

        layout.addLayout(content, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button:
            close_button.clicked.connect(self.close)
        layout.addWidget(buttons)

        self.select_folder_btn.clicked.connect(self.select_folder)
        self.scan_btn.clicked.connect(self.scan_pairs)
        self.preview_btn.clicked.connect(self.preview_dataset)
        self.validate_btn.clicked.connect(self.validate_pairs)
        self.start_btn.clicked.connect(self.start_batch_training)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Training Folder")
        if folder:
            self.folder_input.setText(folder)

    def scan_pairs(self):
        folder_path = self.folder_input.text().strip()
        if not folder_path:
            QMessageBox.warning(self, "Missing Folder", "Select a training folder first.")
            return

        folder = Path(folder_path)
        if not folder.exists():
            QMessageBox.warning(self, "Missing Folder", "The selected folder does not exist.")
            return

        subtitle_exts = self._selected_subtitle_extensions()
        media_by_stem: Dict[str, Path] = {}
        subtitle_by_stem: Dict[str, Path] = {}

        for child in folder.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() in self.MEDIA_EXTENSIONS:
                media_by_stem[child.stem] = child
            elif child.suffix.lower() in subtitle_exts:
                subtitle_by_stem[child.stem] = child

        stems = sorted(set(media_by_stem) | set(subtitle_by_stem))
        self.valid_pairs = []
        self.issues = []

        for stem in stems:
            media_file = media_by_stem.get(stem)
            subtitle_file = subtitle_by_stem.get(stem)
            if media_file and subtitle_file:
                self.valid_pairs.append((media_file, subtitle_file))
            elif media_file and not subtitle_file:
                self.issues.append(f"{media_file.name} -> missing subtitle")
            elif subtitle_file and not media_file:
                self.issues.append(f"{subtitle_file.name} -> missing media")

        self.valid_list.clear()
        self.valid_list.addItems([f"{media.name} <-> {subtitle.name}" for media, subtitle in self.valid_pairs])
        self.issues_list.clear()
        self.issues_list.addItems(self.issues)
        self.dataset_entries = []
        self.detected_languages = set()
        self.execution_mode_label.setText(self.run_mode_combo.currentText())
        self._update_summary()
        self._append_status(f"Scanned {folder} and found {len(self.valid_pairs)} valid pair(s).")

    def preview_dataset(self):
        if not self.valid_pairs:
            QMessageBox.information(self, "No Dataset", "Scan paired files first.")
            return

        preview_lines: List[str] = []
        total_segments = 0
        total_duration = 0.0
        detected_languages: set[str] = set()
        dataset_entries: List[Dict] = []

        for pair_index, (media_file, subtitle_file) in enumerate(self.valid_pairs, start=1):
            try:
                document = SubtitleFormatRegistry.get_adapter_for_path(str(subtitle_file)).import_file(str(subtitle_file))
            except Exception as exc:
                self.issues.append(f"{subtitle_file.name} -> parse failure: {exc}")
                continue

            total_segments += len(document.segments)
            total_duration += sum(segment.duration() for segment in document.segments)
            detected_languages.add(document.language or "auto")
            for segment in document.segments:
                dataset_entries.append(
                    {
                        "original_text": "",
                        "corrected_text": segment.text,
                        "file_path": str(media_file),
                        "start_time": segment.start_time,
                        "end_time": segment.end_time,
                        "confidence": max(segment.confidence, 1.0),
                        "language": segment.language or document.language or "auto",
                    }
                )

            if pair_index <= 5:
                preview_lines.append(media_file.name)
                for segment in document.segments[:3]:
                    preview_lines.append(
                        f"  {self._format_duration(segment.start_time)} -> {self._format_duration(segment.end_time)}"
                    )
                    preview_lines.append(f"  {segment.text}")
                preview_lines.append("")

        self.preview_text.setPlainText("\n".join(preview_lines).strip())
        self.dataset_entries = dataset_entries
        self.detected_languages = detected_languages
        self.estimated_segments_label.setText(str(total_segments))
        self.estimated_duration_label.setText(self._format_duration(total_duration))
        self.issue_count_label.setText(str(len(self.issues)))
        self.detected_languages_label.setText(", ".join(sorted(detected_languages)) if detected_languages else "--")
        self.execution_mode_label.setText(self.run_mode_combo.currentText())
        self.issues_list.clear()
        self.issues_list.addItems(self.issues)
        self._append_status(
            f"Built dataset preview with {len(dataset_entries)} segment example(s) from {len(self.valid_pairs)} pair(s)."
        )

    def start_batch_training(self):
        if not self.valid_pairs:
            QMessageBox.information(self, "Nothing To Train", "Scan a folder with valid pairs first.")
            return

        if not self.dataset_entries:
            self.preview_dataset()
        if not self.dataset_entries:
            QMessageBox.warning(self, "Empty Dataset", "No subtitle segments were found in the scanned pairs.")
            return

        if not self.background_trainer:
            QMessageBox.warning(
                self,
                "Trainer Unavailable",
                "Load or initialize a Whisper model first so the batch dataset can run through the trainer backend.",
            )
            return

        manifest_path = self._save_dataset_manifest()
        run_in_background = self.run_mode_combo.currentText() == "Background"
        selected_model = self.model_combo.currentText()

        try:
            self.background_trainer.train_on_batch_dataset(
                self.dataset_entries,
                base_model=selected_model,
                run_in_background=run_in_background,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Batch Training Failed", f"Could not start batch training:\n{exc}")
            self._append_status(f"Batch training failed to start: {exc}")
            return

        mode_label = "background" if run_in_background else "foreground"
        self.execution_mode_label.setText(self.run_mode_combo.currentText())
        self._append_status(
            f"Started {mode_label} batch training for {len(self.dataset_entries)} segment example(s) using '{selected_model}'."
        )

        QMessageBox.information(
            self,
            "Batch Training Started",
            "Batch training has been started.\n\n"
            f"Pairs: {len(self.valid_pairs)}\n"
            f"Examples: {len(self.dataset_entries)}\n"
            f"Model: {selected_model}\n"
            f"Mode: {self.run_mode_combo.currentText()}\n"
            f"Manifest: {manifest_path}",
        )

    def _selected_subtitle_extensions(self) -> List[str]:
        mode = self.subtitle_formats_combo.currentText()
        if mode == "SRT only":
            return [".srt"]
        if mode == "SMI only":
            return [".smi", ".sami"]
        return [".srt", ".smi", ".sami"]

    def validate_pairs(self):
        if not self.valid_pairs:
            QMessageBox.information(self, "Nothing To Validate", "Scan paired files first.")
            return

        self.preview_dataset()
        if self.issues:
            QMessageBox.warning(
                self,
                "Validation Complete",
                f"Validation found {len(self.issues)} issue(s). Review the issues list before training.",
            )
        else:
            QMessageBox.information(
                self,
                "Validation Complete",
                f"All {len(self.valid_pairs)} pair(s) validated successfully.",
            )

    def _update_summary(self):
        self.valid_pairs_label.setText(str(len(self.valid_pairs)))
        self.issue_count_label.setText(str(len(self.issues)))
        self.estimated_segments_label.setText("0")
        self.estimated_duration_label.setText("00:00")
        self.detected_languages_label.setText("--")
        self.execution_mode_label.setText(self.run_mode_combo.currentText())
        self.preview_text.clear()

    def _grouped_status_widget(self) -> QGroupBox:
        box = QGroupBox("Execution Status")
        layout = QVBoxLayout(box)
        layout.addWidget(self.status_text)
        return box

    def _save_dataset_manifest(self) -> Path:
        base_dir = self.background_trainer.models_dir if self.background_trainer else Path.cwd()
        manifest_dir = Path(base_dir) / "batch_datasets"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / f"batch_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        payload = {
            "created_at": datetime.now().isoformat(),
            "model": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "run_mode": self.run_mode_combo.currentText(),
            "pair_count": len(self.valid_pairs),
            "issue_count": len(self.issues),
            "entries": self.dataset_entries,
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self.last_dataset_manifest = manifest_path
        self._append_status(f"Saved dataset manifest to {manifest_path}")
        return manifest_path

    def _append_status(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
