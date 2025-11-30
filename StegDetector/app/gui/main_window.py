from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QTabWidget,
    QPlainTextEdit,
    QCheckBox,
)

from core.utils_av import (
    is_audio_file,
    is_video_file,
    extract_audio_from_video,
    ensure_dir,
)
from core.audio_detector import analyze_audio
from core.video_detector import analyze_video
from core.stego_audio import embed_lsb_audio, extract_lsb_audio
from core.stego_video import embed_lsb_video, extract_lsb_video


class MainWindow(QMainWindow):
    """
    Main GUI window for the StegDetector tool.

    Tabs:
      - Analysis: run A1/A2/V1/V2 on audio / video
      - Embed:    hide a message in audio, video, or both (single container)
      - Extract:  recover an LSB text payload from audio / video
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Steganography Detector & Stego Tool (Audio & Video)")
        self.setMinimumSize(1050, 700)

        # State
        self.analysis_selected_file: Path | None = None
        self.embed_selected_cover: Path | None = None
        self.extract_selected_file: Path | None = None
        self.embed_cover_is_audio: bool = False

        # Widgets we need to access later
        self.analysis_file_label: QLabel | None = None
        self.analysis_results: QPlainTextEdit | None = None

        self.mode_auto: QRadioButton | None = None
        self.mode_audio_only: QRadioButton | None = None
        self.mode_video_only: QRadioButton | None = None

        self.embed_file_label: QLabel | None = None
        self.embed_type_label: QLabel | None = None
        self.embed_message_video_edit: QPlainTextEdit | None = None
        self.embed_message_audio_edit: QPlainTextEdit | None = None
        self.embed_mode_video_only: QRadioButton | None = None
        self.embed_mode_audio_only: QRadioButton | None = None
        self.embed_mode_both: QRadioButton | None = None
        self.embed_status_label: QLabel | None = None
        self.embed_where_group: QGroupBox | None = None
        self.embed_label_video: QLabel | None = None
        self.embed_label_audio: QLabel | None = None
        self.same_msg_checkbox: QCheckBox | None = None

        self.extract_file_label: QLabel | None = None
        self.extract_message_view: QPlainTextEdit | None = None
        self.extract_mode_auto: QRadioButton | None = None
        self.extract_mode_video: QRadioButton | None = None
        self.extract_mode_audio_track: QRadioButton | None = None
        
        # Tabs + cross-navigation buttons
        self.tabs: QTabWidget | None = None
        self.analysis_tab: QWidget | None = None
        self.embed_tab: QWidget | None = None
        self.extract_tab: QWidget | None = None

        self.btn_go_to_extract: QPushButton | None = None
        self.btn_go_to_analysis: QPushButton | None = None

        self.extract_type_label: QLabel | None = None


        self._apply_style()
        self._build_ui()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _apply_style(self) -> None:
        # Light, simple, "web-like" styling
        self.setStyleSheet(
            """
            QWidget {
                font-family: Segoe UI, Arial;
                font-size: 10pt;
            }
            QMainWindow {
                background-color: #f4f6fb;
            }
            QGroupBox {
                border: 1px solid #d0d4e6;
                border-radius: 6px;
                margin-top: 8px;
                padding: 6px 8px 8px 8px;
                background-color: #ffffff;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border-radius: 6px;
                padding: 6px 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            /* Secondary buttons (navigation) */
            QPushButton#secondaryButton {
                background-color: #ffffff;
                color: #2563eb;
                border-radius: 6px;
                padding: 6px 14px;
                border: 1px solid #2563eb;
            }
            QPushButton#secondaryButton:hover {
                background-color: #eff6ff;
            }
            QPushButton#secondaryButton:pressed {
                background-color: #dbeafe;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin: 2px;
            }
            QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 4px;
            }
            QLabel.type-label {
                color: #4b5563;
                font-style: italic;
            }
            """
        )


    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # Store the QTabWidget and individual tabs on self so that
        # cross-navigation (Go to Analysis / Go to Extract) can work.
        self.tabs = QTabWidget()

        self.analysis_tab = self._build_analysis_tab()
        self.embed_tab = self._build_embed_tab()
        self.extract_tab = self._build_extract_tab()

        self.tabs.addTab(self.analysis_tab, "Analysis")
        self.tabs.addTab(self.embed_tab, "Embed")
        self.tabs.addTab(self.extract_tab, "Extract")

        main_layout.addWidget(self.tabs)


    # ------------------------- Analysis tab ----------------------------
    def _build_analysis_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        
        desc = QLabel("Check if an audio or video file is likely clean or stego.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #4b5563; font-size: 9.5pt; margin-bottom: 4px;")
        layout.addWidget(desc)


        # File selection group
        file_group = QGroupBox("1. Select audio or video file")
        file_layout = QHBoxLayout()
        self.analysis_file_label = QLabel("No file selected.")
        browse_btn = QPushButton("Choose File...")
        browse_btn.clicked.connect(self.on_analysis_browse)

        file_layout.addWidget(self.analysis_file_label, 1)
        file_layout.addWidget(browse_btn)
        file_group.setLayout(file_layout)

        # Mode selection group
        mode_group = QGroupBox("2. Analysis mode")
        mode_layout = QHBoxLayout()
        self.mode_auto = QRadioButton("Auto (recommended)")
        self.mode_audio_only = QRadioButton("Audio only")
        self.mode_video_only = QRadioButton("Video only")
        self.mode_auto.setChecked(True)

        mode_buttons = QButtonGroup(self)
        mode_buttons.addButton(self.mode_auto)
        mode_buttons.addButton(self.mode_audio_only)
        mode_buttons.addButton(self.mode_video_only)

        mode_layout.addWidget(self.mode_auto)
        mode_layout.addWidget(self.mode_audio_only)
        mode_layout.addWidget(self.mode_video_only)
        mode_group.setLayout(mode_layout)

        # Run button
        run_btn = QPushButton("Run Analysis")
        run_btn.clicked.connect(self.on_run_analysis)

        # NEW: button to jump to Extract tab
        self.btn_go_to_extract = QPushButton("Go to Extract")
        self.btn_go_to_extract.setObjectName("secondaryButton")
        self.btn_go_to_extract.setEnabled(False)  # enabled after a file is selected
        self.btn_go_to_extract.clicked.connect(self.on_go_to_extract_clicked)

        btn_row = QHBoxLayout()
        btn_row.addWidget(run_btn)
        btn_row.addWidget(self.btn_go_to_extract)
        btn_row.addStretch()


        # Results viewer
        self.analysis_results = QPlainTextEdit()
        self.analysis_results.setReadOnly(True)

        layout.addWidget(file_group)
        layout.addSpacing(8)
        layout.addWidget(mode_group)
        layout.addSpacing(8)
        layout.addLayout(btn_row)
        layout.addSpacing(8)
        layout.addWidget(self.analysis_results, 1)



        return page

    # --------------------------- Embed tab -----------------------------
    def _build_embed_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        
        desc = QLabel("Hide a secret message inside an audio or video file using LSB steganography.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #4b5563; font-size: 9.5pt; margin-bottom: 4px;")
        layout.addWidget(desc)


        # 1. Cover selection
        file_group = QGroupBox("1. Select cover file (audio or video)")
        file_layout = QVBoxLayout()
        top_row = QHBoxLayout()
        self.embed_file_label = QLabel("No cover selected.")
        browse_btn = QPushButton("Choose Cover...")
        browse_btn.clicked.connect(self.on_embed_browse)
        top_row.addWidget(self.embed_file_label, 1)
        top_row.addWidget(browse_btn)

        self.embed_type_label = QLabel("")
        self.embed_type_label.setObjectName("embed_type_label")

        file_layout.addLayout(top_row)
        file_layout.addWidget(self.embed_type_label)
        file_group.setLayout(file_layout)

        # 2. Where to hide (for videos)
        target_group = QGroupBox("2. Where to hide the message (videos only)")
        self.embed_where_group = target_group
        target_layout = QHBoxLayout()
        self.embed_mode_video_only = QRadioButton("Video frames only")
        self.embed_mode_audio_only = QRadioButton("Audio track only")
        self.embed_mode_both = QRadioButton("Both (one video with stego video+audio)")
        self.embed_mode_both.setChecked(True)

        target_buttons = QButtonGroup(self)
        target_buttons.addButton(self.embed_mode_video_only)
        target_buttons.addButton(self.embed_mode_audio_only)
        target_buttons.addButton(self.embed_mode_both)

        # hook visibility updates
        self.embed_mode_video_only.toggled.connect(self._refresh_embed_visibility)
        self.embed_mode_audio_only.toggled.connect(self._refresh_embed_visibility)
        self.embed_mode_both.toggled.connect(self._refresh_embed_visibility)

        target_layout.addWidget(self.embed_mode_video_only)
        target_layout.addWidget(self.embed_mode_audio_only)
        target_layout.addWidget(self.embed_mode_both)
        target_group.setLayout(target_layout)

        # 3. Messages
        msg_group = QGroupBox("3. Enter secret messages")
        msg_layout = QVBoxLayout()

        self.embed_label_video = QLabel("Message for VIDEO frames (LSB on pixel values):")
        self.embed_message_video_edit = QPlainTextEdit()
        self.embed_message_video_edit.setPlaceholderText(
            "Example: Stego in video frames only..."
        )

        self.embed_label_audio = QLabel(
            "Message for AUDIO track (LSB on audio samples).\n"
            "For audio-only covers, only this message is used.\n"
            "If left empty in 'Both' mode, the video message is reused."
        )
        self.embed_message_audio_edit = QPlainTextEdit()
        self.embed_message_audio_edit.setPlaceholderText(
            "Example: Separate message hidden in audio..."
        )

        self.same_msg_checkbox = QCheckBox("Use same message for video and audio")
        self.same_msg_checkbox.toggled.connect(self._refresh_embed_visibility)

        msg_layout.addWidget(self.embed_label_video)
        msg_layout.addWidget(self.embed_message_video_edit, 1)
        msg_layout.addWidget(self.embed_label_audio)
        msg_layout.addWidget(self.embed_message_audio_edit, 1)
        msg_layout.addWidget(self.same_msg_checkbox)
        msg_group.setLayout(msg_layout)

        # 4. Embed button + status
        bottom_row = QHBoxLayout()
        embed_btn = QPushButton("Embed (LSB)")
        embed_btn.clicked.connect(self.on_embed_clicked)

        self.embed_status_label = QLabel("")
        self.embed_status_label.setObjectName("embed_status_label")

        bottom_row.addWidget(embed_btn)
        bottom_row.addWidget(self.embed_status_label, 1)

        layout.addWidget(file_group)
        layout.addSpacing(8)
        layout.addWidget(target_group)
        layout.addSpacing(8)
        layout.addWidget(msg_group, 1)
        layout.addSpacing(8)
        layout.addLayout(bottom_row)


        # initial visibility (no cover yet -> treat as video, both)
        self._refresh_embed_visibility()

        return page

    # --------------------------- Extract tab ---------------------------
    def _build_extract_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        
        desc = QLabel("Try to recover a hidden LSB text message from an audio or video file.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #4b5563; font-size: 9.5pt; margin-bottom: 4px;")
        layout.addWidget(desc)


        file_group = QGroupBox("1. Select suspected stego file (audio or video)")

        # CHANGE: use VBox + top_row, and add type label
        f_layout = QVBoxLayout()
        top_row = QHBoxLayout()

        self.extract_file_label = QLabel("No file selected.")
        browse_btn = QPushButton("Choose File...")
        browse_btn.clicked.connect(self.on_extract_browse)

        top_row.addWidget(self.extract_file_label, 1)
        top_row.addWidget(browse_btn)

        # New label that will say "Detected as AUDIO file..." or "VIDEO file..."
        self.extract_type_label = QLabel("")
        self.extract_type_label.setObjectName("extract_type_label")

        f_layout.addLayout(top_row)
        f_layout.addWidget(self.extract_type_label)
        file_group.setLayout(f_layout)

    # ... keep the rest of _build_extract_tab exactly as it is


        # Source selection for videos
        src_group = QGroupBox(
            "2. From where to extract (for videos: frames vs audio track)"
        )
        s_layout = QHBoxLayout()
        self.extract_mode_auto = QRadioButton(
            "Auto (audio-only → audio, video → frames + audio track)"
        )   

        self.extract_mode_video = QRadioButton("Video frames")
        self.extract_mode_audio_track = QRadioButton("Audio track of video")
        self.extract_mode_auto.setChecked(True)

        src_buttons = QButtonGroup(self)
        src_buttons.addButton(self.extract_mode_auto)
        src_buttons.addButton(self.extract_mode_video)
        src_buttons.addButton(self.extract_mode_audio_track)

        s_layout.addWidget(self.extract_mode_auto)
        s_layout.addWidget(self.extract_mode_video)
        s_layout.addWidget(self.extract_mode_audio_track)
        src_group.setLayout(s_layout)

        extract_btn = QPushButton("Extract Message (LSB)")
        extract_btn.clicked.connect(self.on_extract_clicked)

        # NEW: button to jump to Analysis tab
        self.btn_go_to_analysis = QPushButton("Go to Analysis")
        self.btn_go_to_analysis.setObjectName("secondaryButton")
        self.btn_go_to_analysis.setEnabled(False)  # enabled after a file is selected
        self.btn_go_to_analysis.clicked.connect(self.on_go_to_analysis_clicked)

        btn_row = QHBoxLayout()
        btn_row.addWidget(extract_btn)
        btn_row.addWidget(self.btn_go_to_analysis)
        btn_row.addStretch()


        self.extract_message_view = QPlainTextEdit()
        self.extract_message_view.setReadOnly(True)

        layout.addWidget(file_group)
        layout.addSpacing(8)
        layout.addWidget(src_group)
        layout.addSpacing(8)
        layout.addLayout(btn_row)
        layout.addSpacing(8)
        layout.addWidget(self.extract_message_view, 1)


        return page


    # ------------------------------------------------------------------
    # Analysis logic
    # ------------------------------------------------------------------
    def on_analysis_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio or video file",
            "",
            "Audio/Video (*.wav *.mp3 *.flac *.ogg *.mp4 *.avi *.mkv *.mov);;All files (*)",
        )
        if not path:
            return

        p = Path(path)
        self.analysis_selected_file = p
        if self.btn_go_to_extract:
            self.btn_go_to_extract.setEnabled(True)



        if self.analysis_file_label:
            self.analysis_file_label.setText(f"Selected: {p}")

              # Keep Extract tab in sync for good UX
        if self.extract_file_label is not None:
            self.extract_selected_file = p
            self.extract_file_label.setText(f"Selected: {p}")
            # NEW:
            self._update_extract_type_label(p)


        if self.analysis_results:
            self.analysis_results.clear()
            self.analysis_results.appendPlainText(f"Analyzing: {p}\n")

    def on_run_analysis(self) -> None:
        if self.analysis_selected_file is None:
            QMessageBox.warning(self, "No file", "Please select a file first.")
            return

        path = str(self.analysis_selected_file)
        is_a = is_audio_file(path)
        is_v = is_video_file(path)
        if not is_a and not is_v:
            QMessageBox.warning(
                self,
                "Unsupported file",
                "File extension not recognized as audio or video.",
            )
            return

        if self.analysis_results:
            self.analysis_results.clear()

        # Decide which analyses to run based on mode + file type
        run_audio = False
        run_video = False

        if self.mode_auto is not None and self.mode_auto.isChecked():
            if is_a and not is_v:
                run_audio = True
            elif is_v:
                run_audio = True
                run_video = True
        elif self.mode_audio_only is not None and self.mode_audio_only.isChecked():
            run_audio = True
        elif self.mode_video_only is not None and self.mode_video_only.isChecked():
            run_video = True

        if run_audio:
            if is_a:
                self._run_audio_analysis(path)
            elif is_v:
                self._run_video_audio_track_analysis(path)

        if run_video and is_v:
            self._run_video_analysis(path)

    def _append_analysis(self, text: str) -> None:
        if self.analysis_results:
            self.analysis_results.appendPlainText(text)

    def _run_audio_analysis(self, audio_path: str) -> None:
        self._append_analysis("=== Audio Analysis ===")
        try:
            res = analyze_audio(audio_path)
        except Exception as e:
            self._append_analysis(f"Error during audio analysis: {e}\n")
            return

        best_score = res.get("best_score")
        best_method = res.get("best_method")
        self._append_analysis(f"Best audio method: {best_method}")
        self._append_analysis(f"Best audio score: {best_score}\n")

        for r in res.get("methods", []):
            self._append_analysis(f"- Method: {r.get('method')}")
            self._append_analysis(f"  Score: {r.get('score')}")
            self._append_analysis(f"  Verdict: {r.get('verdict')}\n")

    def _run_video_analysis(self, video_path: str) -> None:
        self._append_analysis("=== Video Analysis (Frames) ===")
        try:
            res = analyze_video(video_path)
        except Exception as e:
            self._append_analysis(f"Error during video analysis: {e}\n")
            return

        best_score = res.get("best_score")
        best_method = res.get("best_method")
        self._append_analysis(f"Best video method: {best_method}")
        self._append_analysis(f"Best video score: {best_score}\n")

        for r in res.get("methods", []):
            self._append_analysis(f"- Method: {r.get('method')}")
            self._append_analysis(f"  Score: {r.get('score')}")
            self._append_analysis(f"  Verdict: {r.get('verdict')}\n")

    def _run_video_audio_track_analysis(self, video_path: str) -> None:
        self._append_analysis("=== Audio Track from Video ===")
        temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
        ensure_dir(str(temp_dir))
        tmp_wav = temp_dir / "extracted_audio_for_analysis.wav"

        try:
            ok = extract_audio_from_video(video_path, str(tmp_wav))
        except Exception as e:
            self._append_analysis(f"Could not extract audio track: {e}\n")
            return

        if not ok:
            self._append_analysis(
                "Could not extract audio track: Video has no audio track.\n"
            )
            return

        try:
            res = analyze_audio(str(tmp_wav))
        except Exception as e:
            self._append_analysis(f"Error during audio track analysis: {e}\n")
            return

        best_score = res.get("best_score")
        best_method = res.get("best_method")
        self._append_analysis(f"Best audio-track method: {best_method}")
        self._append_analysis(f"Best audio-track score: {best_score}\n")

        for r in res.get("methods", []):
            self._append_analysis(f"- Method: {r.get('method')}")
            self._append_analysis(f"  Score: {r.get('score')}")
            self._append_analysis(f"  Verdict: {r.get('verdict')}\n")

    # ------------------------------------------------------------------
    # Embed visibility helpers
    # ------------------------------------------------------------------
    def _refresh_embed_visibility(self) -> None:
        """
        Show/hide the 'where to hide' group and message textboxes
        depending on whether the current cover is audio or video
        and which radio button is selected.
        """
        if self.embed_where_group is None:
            return

        is_audio_cover = self.embed_cover_is_audio

        # Helper to set "disabled" look for the audio message box
        def _set_audio_box_enabled(enabled: bool) -> None:
            if not self.embed_message_audio_edit:
                return
            self.embed_message_audio_edit.setEnabled(enabled)
            if enabled:
                # reset to default style
                self.embed_message_audio_edit.setStyleSheet("")
            else:
                # light grey background to show it's not usable
                self.embed_message_audio_edit.setStyleSheet(
                    "background-color: #e5e7eb; color: #6b7280;"
                )

        if is_audio_cover:
            # Audio cover: no "where to hide" choices, only audio message box
            self.embed_where_group.setVisible(False)

            if self.embed_label_video:
                self.embed_label_video.setVisible(False)
            if self.embed_message_video_edit:
                self.embed_message_video_edit.setVisible(False)

            if self.embed_label_audio:
                self.embed_label_audio.setText(
                    "Message for AUDIO file (LSB on samples):"
                )
                self.embed_label_audio.setVisible(True)

            if self.embed_message_audio_edit:
                self.embed_message_audio_edit.setVisible(True)

            # Always active (no "same message" option in audio-only mode)
            _set_audio_box_enabled(True)

            if self.same_msg_checkbox:
                self.same_msg_checkbox.setVisible(False)

        else:
            # Video cover
            self.embed_where_group.setVisible(True)

            mode_video = (
                self.embed_mode_video_only.isChecked()
                if self.embed_mode_video_only
                else False
            )
            mode_audio = (
                self.embed_mode_audio_only.isChecked()
                if self.embed_mode_audio_only
                else False
            )
            mode_both = (
                self.embed_mode_both.isChecked() if self.embed_mode_both else False
            )

            # Restore audio label text
            if self.embed_label_audio:
                self.embed_label_audio.setText(
                    "Message for AUDIO track (LSB on audio samples).\n"
                    "For audio-only covers, only this message is used.\n"
                    "If left empty in 'Both' mode, the video message is reused."
                )

            if mode_video:
                # Only video textbox
                if self.embed_label_video:
                    self.embed_label_video.setVisible(True)
                if self.embed_message_video_edit:
                    self.embed_message_video_edit.setVisible(True)

                if self.embed_label_audio:
                    self.embed_label_audio.setVisible(False)
                if self.embed_message_audio_edit:
                    self.embed_message_audio_edit.setVisible(False)

                if self.same_msg_checkbox:
                    self.same_msg_checkbox.setVisible(False)

            elif mode_audio:
                # Only audio textbox
                if self.embed_label_video:
                    self.embed_label_video.setVisible(False)
                if self.embed_message_video_edit:
                    self.embed_message_video_edit.setVisible(False)

                if self.embed_label_audio:
                    self.embed_label_audio.setVisible(True)
                if self.embed_message_audio_edit:
                    self.embed_message_audio_edit.setVisible(True)

                # Active textbox, no "same message" logic
                _set_audio_box_enabled(True)

                if self.same_msg_checkbox:
                    self.same_msg_checkbox.setVisible(False)

            else:
                # Both video+audio
                if self.embed_label_video:
                    self.embed_label_video.setVisible(True)
                if self.embed_message_video_edit:
                    self.embed_message_video_edit.setVisible(True)

                if self.embed_label_audio:
                    self.embed_label_audio.setVisible(True)
                if self.embed_message_audio_edit:
                    self.embed_message_audio_edit.setVisible(True)

                if self.same_msg_checkbox:
                    self.same_msg_checkbox.setVisible(True)

                use_same = (
                    self.same_msg_checkbox.isChecked()
                    if self.same_msg_checkbox
                    else False
                )
                # Grey-out audio text box when same-message is ON
                _set_audio_box_enabled(not use_same)


    # ------------------------------------------------------------------
    # Embed logic
    # ------------------------------------------------------------------
    def on_embed_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select cover file",
            "",
            "Audio/Video (*.wav *.mp3 *.flac *.ogg *.mp4 *.avi *.mkv *.mov);;All files (*)",
        )
        if not path:
            return

        p = Path(path)
        self.embed_selected_cover = p
        if self.embed_file_label:
            self.embed_file_label.setText(f"Cover: {p}")

        is_a = is_audio_file(str(p))
        is_v = is_video_file(str(p))
        self.embed_cover_is_audio = bool(is_a and not is_v)

        kind = "Unknown"
        if is_a and not is_v:
            kind = "Audio file detected – message will be embedded in audio samples."
        elif is_v:
            kind = (
                "Video file detected – choose whether to hide in frames, "
                "audio track, or both."
            )
        if self.embed_type_label:
            self.embed_type_label.setText(kind)

        if self.embed_status_label:
            self.embed_status_label.setText("")

        self._refresh_embed_visibility()

    def on_embed_clicked(self) -> None:
        if self.embed_selected_cover is None:
            QMessageBox.warning(self, "No cover", "Please choose a cover file first.")
            return

        cover_path = self.embed_selected_cover
        is_a = is_audio_file(str(cover_path))
        is_v = is_video_file(str(cover_path))
        if not is_a and not is_v:
            QMessageBox.warning(
                self,
                "Unsupported file",
                "File extension not recognized as audio or video.",
            )
            return

        msg_video = ""
        msg_audio = ""
        if self.embed_message_video_edit and self.embed_message_video_edit.isVisible():
            msg_video = self.embed_message_video_edit.toPlainText().strip()
        if self.embed_message_audio_edit and self.embed_message_audio_edit.isVisible():
            msg_audio = self.embed_message_audio_edit.toPlainText().strip()

        if not msg_video and not msg_audio:
            QMessageBox.warning(
                self,
                "Empty message",
                "Please type at least one non-empty secret message.",
            )
            return

        same_for_both = False
        if self.same_msg_checkbox and self.same_msg_checkbox.isVisible():
            same_for_both = self.same_msg_checkbox.isChecked()

        try:
            if is_a and not is_v:
                # Audio covers: always embed into audio samples
                if not msg_audio:
                    msg_audio = msg_video
                out_path = self._embed_audio_only(cover_path, msg_audio)
            else:
                # Video covers
                mode = "both"
                if (
                    self.embed_mode_video_only is not None
                    and self.embed_mode_video_only.isChecked()
                ):
                    mode = "video"
                elif (
                    self.embed_mode_audio_only is not None
                    and self.embed_mode_audio_only.isChecked()
                ):
                    mode = "audio_track"

                if mode == "video":
                    if not msg_video:
                        msg_video = msg_audio
                    out_path = self._embed_video_frames_only(cover_path, msg_video)
                elif mode == "audio_track":
                    if not msg_audio:
                        msg_audio = msg_video
                    out_path = self._embed_video_audio_only(cover_path, msg_audio)
                else:  # both
                    if same_for_both:
                        if not msg_video and msg_audio:
                            msg_video = msg_audio
                        if not msg_video:
                            raise ValueError(
                                "Please enter at least one message for video/audio."
                            )
                        msg_audio = msg_video
                    else:
                        if not msg_video and msg_audio:
                            msg_video = msg_audio
                        if not msg_audio and msg_video:
                            msg_audio = msg_video

                    out_path = self._embed_video_both_single_file(
                        cover_path, msg_video, msg_audio
                    )

        except Exception as e:
            QMessageBox.critical(self, "Embedding failed", str(e))
            return

        if self.embed_status_label:
            self.embed_status_label.setText(f"Created stego file: {out_path}")
            # nice green-ish success color
            self.embed_status_label.setStyleSheet("color: #059669;")



        # Also make it easy to immediately extract from this file
        self.extract_selected_file = out_path
        if self.extract_file_label:
            self.extract_file_label.setText(f"Selected: {out_path}")
                    # NEW:
            self._update_extract_type_label(out_path)

 # (you might already sync analysis_selected_file here, if not add:)
        self.analysis_selected_file = out_path
        if self.analysis_file_label:
            self.analysis_file_label.setText(f"Selected: {out_path}")
            
         # Enable cross-navigation buttons
        if self.btn_go_to_extract:
            self.btn_go_to_extract.setEnabled(True)
        if self.btn_go_to_analysis:
            self.btn_go_to_analysis.setEnabled(True)

        # Configure radios on Extract tab for this new stego file
        self._configure_extract_radios_for_path(out_path)
           
        QMessageBox.information(
            self,
            "Embedding done",
            f"Secret message(s) embedded into:\n{out_path}",
        )

    def on_go_to_extract_clicked(self) -> None:
        """
        From Analysis tab → switch to Extract tab,
        carrying over the currently selected file.
        """
        if self.analysis_selected_file is None:
            QMessageBox.information(self, "No file", "Please choose a file first.")
            return

        # Sync extract state
        self.extract_selected_file = self.analysis_selected_file
        if self.extract_file_label:
            self.extract_file_label.setText(f"Selected: {self.analysis_selected_file}")
        self._update_extract_type_label(self.analysis_selected_file)
        self._configure_extract_radios_for_path(self.analysis_selected_file)

        # Switch tab if available
        if self.tabs is not None and self.extract_tab is not None:
            self.tabs.setCurrentWidget(self.extract_tab)

    def on_go_to_analysis_clicked(self) -> None:
        """
        From Extract tab → switch to Analysis tab,
        carrying over the currently selected file.
        """
        if self.extract_selected_file is None:
            QMessageBox.information(self, "No file", "Please select a file first.")
            return

        self.analysis_selected_file = self.extract_selected_file
        if self.analysis_file_label:
            self.analysis_file_label.setText(f"Selected: {self.analysis_selected_file}")

        # Switch tab if available
        if self.tabs is not None and self.analysis_tab is not None:
            self.tabs.setCurrentWidget(self.analysis_tab)




    def _embed_audio_only(self, cover: Path, message: str) -> Path:
        out_path = cover.with_name(cover.stem + "_embedded.wav")
        ensure_dir(str(out_path.parent))
        embed_lsb_audio(str(cover), str(out_path), message)
        return out_path

    def _embed_video_frames_only(self, cover: Path, message: str) -> Path:
        out_path = cover.with_name(cover.stem + "_embedded_video.avi")
        ensure_dir(str(out_path.parent))
        embed_lsb_video(str(cover), str(out_path), message)
        return out_path

    def _embed_video_audio_only(self, cover: Path, message: str) -> Path:
        """
        Only modifies the AUDIO track; video frames are kept as-is.
        Output: single video+audio file with stego audio.
        """
        temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
        ensure_dir(str(temp_dir))
        src_audio = temp_dir / "cover_audio.wav"
        stego_audio = temp_dir / "cover_audio_stego.wav"

        ok = extract_audio_from_video(str(cover), str(src_audio))
        if not ok:
            raise RuntimeError("This video has no audio track to hide a message in.")

        embed_lsb_audio(str(src_audio), str(stego_audio), message)

        # Combine original video stream + stego audio into a single container.
        # Use MKV with PCM audio so LSBs are preserved.
        out_path = cover.with_name(cover.stem + "_embedded_audio_only.mkv")
        self._mux_video_and_audio(cover, stego_audio, out_path)
        return out_path

    def _embed_video_both_single_file(
        self, cover: Path, msg_video: str, msg_audio: str
    ) -> Path:
        """
        Embed one message in VIDEO frames + another in AUDIO track,
        and output ONE video file containing both.
        """
        temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
        ensure_dir(str(temp_dir))

        # 1) embed into video frames (lossless PNG codec in AVI)
        stego_video = temp_dir / "cover_video_stego.avi"
        embed_lsb_video(str(cover), str(stego_video), msg_video)

        # 2) extract original audio and embed msg_audio
        src_audio = temp_dir / "cover_audio.wav"
        stego_audio = temp_dir / "cover_audio_stego.wav"
        ok = extract_audio_from_video(str(cover), str(src_audio))
        if not ok:
            raise RuntimeError(
                "Cover video has no audio track – cannot embed into both video and audio."
            )
        embed_lsb_audio(str(src_audio), str(stego_audio), msg_audio)

        # 3) mux stego video + stego audio into a single MKV WITHOUT re-encoding video
        out_path = cover.with_name(cover.stem + "_embedded_both.mkv")
        self._mux_video_and_audio(stego_video, stego_audio, out_path)
        return out_path

    def _mux_video_and_audio(
        self, video_path: Path | str, audio_path: Path | str, output_path: Path | str
    ) -> Path:
        """
        Use ffmpeg to combine a video stream and an audio stream into a single file.

        - Video is copied (no re-encode) so VIDEO LSB stego survives.
        - Audio is stored as 16-bit PCM so AUDIO LSB stego survives.
        """
        from shutil import which

        video_path = str(video_path)
        audio_path = str(audio_path)
        output_path = str(output_path)

        if which("ffmpeg") is None:
            raise RuntimeError(
                "ffmpeg was not found on your system. Please install ffmpeg and "
                "make sure it is on PATH to create a single video+audio stego file."
            )

        ensure_dir(str(Path(output_path).parent))

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-i",
            audio_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",        # keep video bit-exact (PNG in AVI)
            "-c:a",
            "pcm_s16le",   # lossless audio, LSB-safe
            output_path,
        ]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg failed while combining video and audio.\n\n"
                f"Command: {' '.join(cmd)}\n\n"
                f"Error:\n{proc.stderr}"
            )

        return Path(output_path)



    # ------------------------------------------------------------------
    # Extraction logic
    # ------------------------------------------------------------------
        
        
        # ------------------------------------------------------------------
    # Helper: show file type on Extract tab
    # ------------------------------------------------------------------
    def _update_extract_type_label(self, path: Path | str) -> None:
        if self.extract_type_label is None:
            return

        p_str = str(path)
        is_a = is_audio_file(p_str)
        is_v = is_video_file(p_str)

        if is_a and not is_v:
            msg = "Detected as AUDIO file – message will be extracted from audio samples."
        elif is_v:
            msg = "Detected as VIDEO file – you can extract from frames or from the audio track."
        else:
            msg = "File type not recognized as standard audio/video by extension."

        self.extract_type_label.setText(msg)



        # ---------- helper used by multiple places ----------
    def _configure_extract_radios_for_path(self, p: Path | str) -> None:
        """
        Enable/disable extract radio buttons and set the Auto text
        depending on whether the file is audio-only or video.
        """
        is_a = is_audio_file(str(p))
        is_v = is_video_file(str(p))

        # always default to Auto when a new file is chosen
        if self.extract_mode_auto:
            self.extract_mode_auto.setChecked(True)

        if is_a and not is_v:
            # Pure audio file → only audio extraction makes sense
            if self.extract_mode_auto:
                self.extract_mode_auto.setText(
                    "Auto (audio-only file – decode audio samples)"
                )
            if self.extract_mode_video:
                self.extract_mode_video.setEnabled(False)
            if self.extract_mode_audio_track:
                self.extract_mode_audio_track.setEnabled(False)

        elif is_v:
            # Video file → allow all three options
            if self.extract_mode_auto:
                self.extract_mode_auto.setText(
                    "Auto (video file – extract from frames AND audio track)"
                )
            if self.extract_mode_video:
                self.extract_mode_video.setEnabled(True)
            if self.extract_mode_audio_track:
                self.extract_mode_audio_track.setEnabled(True)

        else:
            # Unknown extension → leave everything enabled and fall back
            if self.extract_mode_auto:
                self.extract_mode_auto.setText(
                    "Auto (audio-only → audio, video → frames + audio track)"
                )
            if self.extract_mode_video:
                self.extract_mode_video.setEnabled(True)
            if self.extract_mode_audio_track:
                self.extract_mode_audio_track.setEnabled(True)

    
    def on_extract_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select stego file",
            "",
            "Audio/Video (*.wav *.mp3 *.flac *.ogg *.mp4 *.avi *.mkv *.mov);;All files (*)",
        )
        if not path:
            return

        p = Path(path)

        # Set extract state + label
        self.extract_selected_file = p
        if self.extract_file_label:
            self.extract_file_label.setText(f"Selected: {p}")

        # Show detected type (audio / video) under the file label
        self._update_extract_type_label(p)

        # Configure the radio buttons (Auto / Video frames / Audio track)
        self._configure_extract_radios_for_path(p)

        # Sync back to Analysis tab for convenience
        self.analysis_selected_file = p
        if self.analysis_file_label:
            self.analysis_file_label.setText(f"Selected: {p}")

        # Clear any previous extracted message
        if self.extract_message_view:
            self.extract_message_view.clear()

        # Enable cross-navigation buttons if they exist
        if self.btn_go_to_analysis:
            self.btn_go_to_analysis.setEnabled(True)
        if self.btn_go_to_extract:
            self.btn_go_to_extract.setEnabled(True)




    def on_extract_clicked(self) -> None:
        """
        Extract LSB message(s) from the selected file.

        Behaviour:
        - Audio-only file:
            * Auto / any mode  → audio LSB.
        - Video file:
            * Video frames     → only video LSB.
            * Audio track      → only audio-track LSB.
            * Auto             → BOTH (video frames AND audio track),
                                  shown together in the text box.
        """
        if self.extract_selected_file is None:
            QMessageBox.warning(self, "No file", "Please select a stego file first.")
            return

        path = str(self.extract_selected_file)
        is_a = is_audio_file(path)
        is_v = is_video_file(path)
        if not is_a and not is_v:
            QMessageBox.warning(
                self,
                "Unsupported file",
                "File extension not recognized as audio or video.",
            )
            return

        # which mode did the user choose?
        mode = "auto"
        if self.extract_mode_video is not None and self.extract_mode_video.isChecked():
            mode = "video"
        elif (
            self.extract_mode_audio_track is not None
            and self.extract_mode_audio_track.isChecked()
        ):
            mode = "audio_track"

        # clear previous output
        if self.extract_message_view:
            self.extract_message_view.clear()

        try:
            # ------------------ AUDIO-ONLY FILE ------------------
            if is_a and not is_v:
                # For an audio file, whatever the radio, decode audio LSB.
                msg = extract_lsb_audio(path)
                if not msg:
                    msg = (
                        "[No message detected using 1-LSB extraction. "
                        "Either there is no hidden ASCII text, or a different stego scheme was used.]"
                    )
                if self.extract_message_view:
                    self.extract_message_view.setPlainText(msg)
                return

            # ------------------ VIDEO FILE -----------------------
            pieces = []  # list of (label, message)

            if mode == "video":
                # only video frames
                v_msg = extract_lsb_video(path)
                pieces.append(("Video frames", v_msg))

            elif mode == "audio_track":
                # only audio track
                a_msg = self._extract_from_video_audio_track(path)
                pieces.append(("Audio track", a_msg))

            else:
                # Auto on a video: extract from BOTH frames and audio track
                v_msg = extract_lsb_video(path)
                pieces.append(("Video frames", v_msg))

                a_msg = self._extract_from_video_audio_track(path)
                pieces.append(("Audio track", a_msg))

            # format output nicely
            if not pieces:
                text = (
                    "[No message detected using 1-LSB extraction. "
                    "Either there is no hidden ASCII text, or a different stego scheme was used.]"
                )
            elif len(pieces) == 1:
                # just one message (video-only or audio-only)
                label, msg = pieces[0]
                text = msg or (
                    "[No message detected using 1-LSB extraction. "
                    "Either there is no hidden ASCII text, or a different stego scheme was used.]"
                )
            else:
                # we have both video and audio messages
                blocks = []
                for label, msg in pieces:
                    blocks.append(f"=== {label} ===")
                    # if msg is empty or whitespace, show a short notice
                    msg = msg if msg is not None else ""
                    blocks.append(msg.strip() or "[No valid LSB text payload found]")
                    blocks.append("")
                text = "\n".join(blocks)

            if self.extract_message_view:
                self.extract_message_view.setPlainText(text)

        except Exception as e:
            QMessageBox.critical(self, "Extraction failed", str(e))
            return



    def _extract_from_video_audio_track(self, video_path: str) -> str:
        temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
        ensure_dir(str(temp_dir))
        tmp_wav = temp_dir / "extracted_audio_for_extract.wav"

        ok = extract_audio_from_video(video_path, str(tmp_wav))
        if not ok:
            return "[Video has no audio track to extract from.]"

        return extract_lsb_audio(str(tmp_wav))
