# streamlit_app.py
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

from auth_db import init_db, create_user, verify_user
from core.audio_detector import analyze_audio
from core.video_detector import analyze_video
from core.stego_audio import embed_lsb_audio, extract_lsb_audio
from core.stego_video import embed_lsb_video, extract_lsb_video
from core.utils_av import extract_audio_from_video, ensure_dir


# Practical limits for the public Streamlit demo (Cloud)
MAX_FILE_BYTES = 50 * 1024 * 1024       # 50 MB for analyze / embed
MAX_AUDIO_MESSAGE_CHARS = 5000          # safe upper bound for audio messages
MAX_VIDEO_MESSAGE_CHARS = 20000         # safe upper bound for video messages

# Larger limit specifically for extraction tab
MAX_EXTRACT_FILE_BYTES = 300 * 1024 * 1024  # 300 MB for Extract tab


# Global CSS tweaks for a slightly softer UI
st.markdown(
    """
    <style>
    /* Soften the Quick help expander */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #e5e7eb !important;
        background-color: #fafafa !important;
    }
    div[data-testid="stExpander"] > details {
        padding: 0.25rem 0.75rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- UI/UX HELPERS ----------

from shutil import which

def has_ffmpeg() -> bool:
    """Return True if ffmpeg is available on PATH."""
    return which("ffmpeg") is not None

def reset_app_state() -> None:
    """Clear shared file and stego-related session keys without affecting login state."""
    for key in (
        "shared_file_bytes",
        "shared_file_name",
        "shared_file_kind",
        "shared_file_suffix",
        "stego_bytes",
        "stego_filename",
        "has_stego",
        # include obvious temporary flags if present
        "embed_single_message",
        "embed_both_same",
        "embed_video_frames_msg",
        "embed_audio_track_msg",
        "use_same_message_checkbox",
        "embed_video_mode",
        "extract_video_mode",
    ):
        if key in st.session_state:
            st.session_state.pop(key, None)

def inject_global_css():
    """Inject custom CSS for a polished look."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #f5f7fb;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e5e7eb;
        }
        section.main > div {
            padding-top: 1rem;
        }
        .stButton > button {
            border-radius: 999px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_global_styles():
    """Make text areas more visible with stronger borders and subtle background."""
    st.markdown(
        """
        <style>
        /* All multi-line text areas */
        .stTextArea textarea {
            border: 2px solid #2563eb !important;   /* blue border */
            border-radius: 8px !important;
            background-color: #f9fafb !important;   /* very light gray */
            font-size: 0.95rem !important;
        }

        /* Labels above text areas */
        .stTextArea label {
            font-weight: 600 !important;
        }

        /* Code blocks for recovered messages */
        [data-testid="stCodeBlock"] {
            border: 2px solid #2563eb !important;
            border-radius: 8px !important;
            background-color: #f9fafb !important;
            padding: 0.5rem 0.75rem !important;
        }
        [data-testid="stCodeBlock"] pre {
            color: #111827 !important;
            font-size: 0.95rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- FILE TYPE HELPERS ----------

def classify_file_type(filename: str) -> Tuple[Optional[str], str]:
    """
    Decide whether a file should be treated as audio or video based on its extension.

    Returns:
        (kind, suffix)
        kind in {"audio", "video", None}
    """
    suffix = Path(filename).suffix.lower()
    audio_exts = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
    video_exts = {".mp4", ".avi", ".mkv", ".mov", ".flv"}

    if suffix in audio_exts:
        return "audio", suffix
    if suffix in video_exts:
        return "video", suffix
    return None, suffix


# ---------- SHARED FILE STATE (PERSIST ACROSS TABS) ----------

def init_app_state():
    if "logged_in_user" not in st.session_state:
        st.session_state["logged_in_user"] = None

    # Shared uploaded file for all tabs
    defaults = {
        "shared_file_bytes": None,
        "shared_file_name": None,
        "shared_file_kind": None,   # "audio" or "video"
        "shared_file_suffix": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def update_shared_file(uploaded_file, max_bytes: int = MAX_FILE_BYTES) -> None:
    """
    Store the uploaded file (bytes + metadata) in session_state so that
    all tabs can reuse it.

    max_bytes:
        - default: MAX_FILE_BYTES (50 MB) for Analyze and Embed tabs
        - Extract tab will explicitly override this to MAX_EXTRACT_FILE_BYTES (300 MB)
    """
    if uploaded_file is None:
        return

    # Reject very large files for the online demo, unless max_bytes is None
    if (
        max_bytes is not None
        and getattr(uploaded_file, "size", None) is not None
        and uploaded_file.size > max_bytes
    ):
        mb = max_bytes / (1024 * 1024)
        st.error(
            f"File is too large for the online demo (limit {mb:.0f} MB). "
            "Please use a shorter or lower-resolution audio/video file."
        )
        return

    kind, suffix = classify_file_type(uploaded_file.name)
    if kind is None:
        st.error(
            f"Unsupported file type: {suffix}. "
            "Please upload audio (wav/mp3/flac/ogg/m4a) or video (mp4/avi/mkv/mov/flv)."
        )
        return

    st.session_state["shared_file_bytes"] = uploaded_file.getvalue()
    st.session_state["shared_file_name"] = uploaded_file.name
    st.session_state["shared_file_kind"] = kind
    st.session_state["shared_file_suffix"] = suffix


def has_shared_file() -> bool:
    return st.session_state.get("shared_file_bytes") is not None



def make_temp_file_from_shared() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Materialize the shared file bytes into a real temp file on disk.
    Returns (temp_path, kind, suffix) or (None, None, None) if no file.
    """
    if not has_shared_file():
        return None, None, None

    data = st.session_state["shared_file_bytes"]
    suffix = st.session_state["shared_file_suffix"]
    kind = st.session_state["shared_file_kind"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        temp_path = tmp.name

    return temp_path, kind, suffix


def show_shared_file_info():
    name = st.session_state.get("shared_file_name")
    kind = st.session_state.get("shared_file_kind")
    if not name:
        st.info("No file selected yet. Upload a file in any tab and it will be shared here.")
        return
    label = "Audio" if kind == "audio" else "Video" if kind == "video" else "Unknown"
    st.success(
        f"Current shared file: **{name}**  \n"
        f"Type: **{label}**  \n"
        "This file is reused across all tabs."
    )


# ---------- VIDEO AUDIO-TRACK HELPERS ----------

def _mux_video_and_audio(video_path: Path | str, audio_path: Path | str, output_path: Path | str) -> Path:
    """
    Use ffmpeg to combine a video stream and an audio stream into a single file.

    - Video is copied (no re-encode) so VIDEO LSB stego survives.
    - Audio is stored lossless so AUDIO LSB stego survives.
    """
    video_path = str(video_path)
    audio_path = str(audio_path)
    output_path = str(output_path)

    if not has_ffmpeg():
        raise RuntimeError(
            "ffmpeg is required to mux video and audio but was not found in PATH."
        )

    # Use FLAC for lossless audio in MP4, or use MKV with PCM for maximum compatibility
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",        # keep video codec as-is
        "-c:a", "flac",        # lossless FLAC codec preserves LSBs
        "-shortest",           # use shortest stream to avoid sync issues
        "-fflags", "+bitexact", # preserve exact bitstream
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


def embed_video_frames_only(cover_path: str, stego_path: str, message: str) -> None:
    """
    Standard VIDEO-only stego: message in the LSBs of video frames, no audio track.
    """
    embed_lsb_video(cover_path, stego_path, message)


def embed_video_audio_only(cover_path: str, stego_path: str, message: str) -> None:
    """
    Only modifies the AUDIO track of the given video; frames are kept as-is.

    Output: single video+audio file with stego audio in PCM format.
    """
    temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
    ensure_dir(str(temp_dir))
    src_audio = temp_dir / "cover_audio.wav"
    stego_audio = temp_dir / "cover_audio_stego.wav"

    try:
        extract_audio_from_video(str(cover_path), str(src_audio))
    except Exception as e:
        raise RuntimeError("This video has no audio track to hide a message in.") from e

    embed_lsb_audio(str(src_audio), str(stego_audio), message)
    _mux_video_and_audio(cover_path, stego_audio, stego_path)


def embed_video_both(cover_path: str, stego_path: str, msg_video: str, msg_audio: str) -> None:
    """
    Embed one message in VIDEO frames + another in AUDIO track,
    and output ONE video file containing both.
    """
    temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
    ensure_dir(str(temp_dir))

    # 1) embed into video frames (lossless PNG codec in AVI)
    stego_video_path = temp_dir / "cover_video_stego.avi"
    embed_lsb_video(str(cover_path), str(stego_video_path), msg_video)

    # 2) extract original audio and embed msg_audio
    src_audio = temp_dir / "cover_audio.wav"
    stego_audio = temp_dir / "cover_audio_stego.wav"

    try:
        extract_audio_from_video(str(cover_path), str(src_audio))
    except Exception as e:
        raise RuntimeError(
            "Cover video has no audio track – cannot embed into both video and audio."
        ) from e

    embed_lsb_audio(str(src_audio), str(stego_audio), msg_audio)

    # 3) mux stego video + stego audio into a single MKV WITHOUT re-encoding video
    _mux_video_and_audio(stego_video_path, stego_audio, stego_path)


def extract_message_from_video_audio(video_path: str) -> str:
    """
    Extract LSB text message from the AUDIO TRACK of a video, if present.
    """
    temp_dir = Path(tempfile.gettempdir()) / "stegdetector_tmp"
    ensure_dir(str(temp_dir))
    src_audio = temp_dir / "extract_audio.wav"

    try:
        extract_audio_from_video(str(video_path), str(src_audio))
    except Exception:
        return "[No audio track found or failed to extract audio from this video]"

    msg = extract_lsb_audio(str(src_audio))
    return msg


# ---------- AUTH SCREENS ----------

def show_auth_page():
    st.title("StegDetector – Login / Sign Up")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    # --- LOGIN TAB ---
    with tab_login:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("Log in"):
            if not login_username or not login_password:
                st.error("Please enter both username and password.")
            else:
                if verify_user(login_username, login_password):
                    st.session_state["logged_in_user"] = login_username
                    st.success(f"Logged in as {login_username}")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    # --- SIGNUP TAB ---
    with tab_signup:
        st.subheader("Create a new account")
        signup_username = st.text_input("Username", key="signup_username")
        signup_password = st.text_input("Password (Min 8 characters, at least 1 uppercase, 1 lowercase, 1 number, 1 special character)", type="password", key="signup_password")
        signup_password2 = st.text_input("Confirm Password", type="password", key="signup_password2")

        if st.button("Sign up"):
            if not signup_username or not signup_password or not signup_password2:
                st.error("Please fill all fields.")
            elif signup_password != signup_password2:
                st.error("Passwords do not match.")
            else:
                success, msg = create_user(signup_username, signup_password)
                if success:
                    st.success(msg)
                    # Auto-login after successful sign-up
                    st.session_state["logged_in_user"] = signup_username
                    st.rerun()
                else:
                    st.error(msg)


# ---------- MAIN APP (AFTER LOGIN) ----------

def show_analyze_tab():
    st.header("Analyze File for Steganography")
    st.write(
        "Upload an audio or video file and run our steganalysis methods to estimate "
        "whether it is likely to contain hidden data."
    )
    st.info("Tip: the uploaded file is shared with the *Embed* and *Extract* tabs.")

    uploaded = st.file_uploader(
        "Upload or replace an audio/video file to analyze",
        type=["wav", "mp3", "flac", "ogg", "m4a", "mp4", "avi", "mkv", "mov", "flv"],
        key="file_analyze",
    )
    if uploaded is not None:
        update_shared_file(uploaded)

    show_shared_file_info()

    if st.button("Run analysis", use_container_width=True):
        if not has_shared_file():
            st.error("Please upload an audio or video file first.")
            return

        temp_path, kind, _ = make_temp_file_from_shared()
        if temp_path is None:
            st.error("Internal error: shared file missing.")
            return

        try:
            if kind == "audio":
                st.info("Detected: **Audio file** – running audio steganalysis.")
                result = analyze_audio(temp_path)
            elif kind == "video":
                st.info("Detected: **Video file** – running video steganalysis on frames.")
                result = analyze_video(temp_path)
            else:
                st.error("Unsupported file type.")
                return

            st.subheader("Analysis Result")
            st.json(result)
        except Exception as e:
            st.error(f"Error during analysis: {e}")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def show_embed_tab():
    st.header("Embed a Secret Message")
    st.write(
        "Choose a cover audio or video file and hide a secret text message using LSB "
        "steganography. You can later test it with the **Analyze** and **Extract** tabs."
    )

    st.info(
        "Performance tip (online demo):\n\n"
        "- Embedding in **audio only** or **video frames only** usually keeps file sizes moderate.\n"
        "- A **video without audio** also behaves normally after embedding.\n"
        "- The heaviest case is a **video with audio where both streams carry hidden data**; "
        "these stego files can become much larger and may take longer for Streamlit to prepare "
        "and start downloading.\n\n"
        "For smoother use on the website, prefer very short, low-resolution clips "
        "(for example a few seconds at 240p), or a single stream (audio-only or video-only). "
        "The three sample files provided with our Moodle submission cover the main use cases "
        "and are convenient for testing the web app. For larger or higher-quality videos, "
        "it is more practical to run the local StegDetector executable instead of the online demo."
    )

    uploaded = st.file_uploader(
        "Upload or replace a COVER file (audio or video)",
        type=["wav", "mp3", "flac", "ogg", "m4a", "mp4", "avi", "mkv", "mov", "flv"],
        key="file_embed",
    )
    if uploaded is not None:
        update_shared_file(uploaded)

    show_shared_file_info()

    kind = st.session_state.get("shared_file_kind")

    if not has_shared_file():
        st.info("Upload a cover file above to enable embedding.")
        return

    video_mode = None
    if kind == "video":
        video_mode = st.radio(
            "For video covers: where to hide the message?",
            ["Video frames only", "Audio track only", "Both frames + audio"],
            key="embed_video_mode",
        )

    # Handle message input based on video mode
    message = None
    msg_video = None
    msg_audio = None

    if kind == "audio" or video_mode == "Video frames only" or video_mode == "Audio track only":
        # Single message for audio or single video/audio mode
        message = st.text_area(
            "Secret message to hide",
            placeholder="Type the secret text you want to embed inside the audio/video file...",
            height=150,
            key="embed_single_message",
        )
    elif video_mode == "Both frames + audio":
        # Two message mode with option to use same message
        use_same_message = st.checkbox("Use the same message for both video and audio frames", value=True, key="use_same_message_checkbox")
        
        if use_same_message:
            message = st.text_area(
                "Secret message to hide (for both video frames and audio track)",
                placeholder="This same message will be embedded into both frames and audio.",
                height=150,
                key="embed_both_same",
            )
        else:
            col1, col2 = st.columns(2)
            with col1:
                msg_video = st.text_area(
                    "Secret message to hide in VIDEO FRAMES",
                    placeholder="Message for video frames...",
                    height=150,
                    key="embed_video_frames_msg",
                )
            with col2:
                msg_audio = st.text_area(
                    "Secret message to hide in AUDIO TRACK",
                    placeholder="Message for audio track...",
                    height=150,
                    key="embed_audio_track_msg",
                )

    if st.button("Embed message", use_container_width=True):
        # Validate messages
        if kind == "audio" or video_mode in ["Video frames only", "Audio track only"]:
            if not message:
                st.error("Please enter a message to hide.")
                return
        elif video_mode == "Both frames + audio":
            use_same_message = st.session_state.get("embed_both_same_message", st.session_state.get("use_same_message_checkbox", True))
            if use_same_message:
                if not message:
                    st.error("Please enter a message to hide.")
                    return
            else:
                if not msg_video or msg_video.strip() == "":
                    st.error("Please enter a message for video frames.")
                    return
                if not msg_audio or msg_audio.strip() == "":
                    st.error("Please enter a message for audio track.")
                    return

        # NEW: practical message-length limits for the online demo
        if kind == "audio":
            if len(message) > MAX_AUDIO_MESSAGE_CHARS:
                st.error(
                    f"Message is too long for this audio in the online demo. "
                    f"Please keep audio messages under {MAX_AUDIO_MESSAGE_CHARS} characters."
                )
                return
        elif kind == "video":
            if video_mode in ["Video frames only", "Audio track only"]:
                if len(message) > MAX_VIDEO_MESSAGE_CHARS:
                    st.error(
                        f"Message is too long for this video in the online demo. "
                        f"Please keep each video message under {MAX_VIDEO_MESSAGE_CHARS} characters."
                    )
                    return
            elif video_mode == "Both frames + audio":
                use_same_message = st.session_state.get(
                    "embed_both_same_message",
                    st.session_state.get("use_same_message_checkbox", True)
                )
                if use_same_message:
                    if len(message) > MAX_VIDEO_MESSAGE_CHARS:
                        st.error(
                            f"Message is too long for this video in the online demo. "
                            f"Please keep each video message under {MAX_VIDEO_MESSAGE_CHARS} characters."
                        )
                        return
                else:
                    if len(msg_video) > MAX_VIDEO_MESSAGE_CHARS or len(msg_audio) > MAX_VIDEO_MESSAGE_CHARS:
                        st.error(
                            f"One of the messages is too long for this video in the online demo. "
                            f"Please keep each video message under {MAX_VIDEO_MESSAGE_CHARS} characters."
                        )
                        return

        temp_path, kind, suffix = make_temp_file_from_shared()
        if temp_path is None:
            st.error("Internal error: shared file missing.")
            return

        # Decide output extension + friendly download name
        original_name = st.session_state.get("shared_file_name") or "cover"
        base_stem = Path(original_name).stem

        if kind == "audio":
            out_ext = suffix  # keep same extension
        else:  # video
            if video_mode is None:
                st.error("Please choose where to embed inside the video.")
                return
            if video_mode == "Video frames only":
                out_ext = ".mkv"
            elif video_mode == "Audio track only":
                out_ext = ".mkv"
            else:
                out_ext = ".mkv"

        with tempfile.NamedTemporaryFile(delete=False, suffix=out_ext) as tmp:
            stego_path = tmp.name

        try:
            with st.spinner("Embedding your secret message into the file. This may take several seconds for videos..."):
                if kind == "audio":
                    st.info("Embedding into AUDIO samples")
                    try:
                        embed_lsb_audio(temp_path, stego_path, message)
                    except ValueError as e:
                        st.error(str(e))
                        return
                    except Exception as e:
                        st.error(f"Error during embedding: {e}")
                        return
                elif kind == "video":
                    if video_mode == "Video frames only":
                        if not has_ffmpeg():
                            st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                            return
                        st.info("Embedding into VIDEO FRAMES only.")
                        try:
                            embed_video_frames_only(temp_path, stego_path, message)
                        except ValueError as e:
                            st.error(str(e))
                            return
                        except Exception as e:
                            st.error(f"Error during embedding: {e}")
                            return
                    elif video_mode == "Audio track only":
                        if not has_ffmpeg():
                            st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                            return
                        st.info("Embedding into AUDIO TRACK only.")
                        try:
                            embed_video_audio_only(temp_path, stego_path, message)
                        except ValueError as e:
                            st.error(str(e))
                            return
                        except Exception as e:
                            st.error(f"Error during embedding: {e}")
                            return
                    else:  # both
                        if not has_ffmpeg():
                            st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                            return
                        st.info("Embedding into BOTH video frames and audio track.")
                        use_same_msg = st.session_state.get("use_same_message_checkbox", True)
                        try:
                            if use_same_msg:
                                embed_video_both(temp_path, stego_path, message, message)
                            else:
                                embed_video_both(temp_path, stego_path, msg_video, msg_audio)
                        except ValueError as e:
                            st.error(str(e))
                            return
                        except Exception as e:
                            st.error(f"Error during embedding: {e}")
                            return
                else:
                    st.error("Unsupported file type.")
                    return

            st.success("Message embedded successfully.")
            # Small visual feedback for the user
            st.balloons()

            download_name = f"{base_stem}_stego{out_ext}"
            with open(stego_path, "rb") as f:
                stego_bytes = f.read()
            
            # Store in session state for persistent download
            st.session_state["stego_bytes"] = stego_bytes
            st.session_state["stego_filename"] = download_name
            st.session_state["has_stego"] = True

        except Exception as e:
            st.error(f"Error during embedding: {e}")
        finally:
            for p in (temp_path, stego_path):
                try:
                    os.remove(p)
                except OSError:
                    pass

    # Persistent download section
    if st.session_state.get("has_stego") and st.session_state.get("stego_bytes") is not None:
        st.info(
            "Click **Download stego file** below. "
            "If your browser does not start downloading within a few seconds, "
            "click the button again."
        )
        st.download_button(
            label="Download stego file",
            data=st.session_state["stego_bytes"],
            file_name=st.session_state.get("stego_filename", "stego_output"),
            key="download_stego_button",
            use_container_width=True,
        )


def show_extract_tab():
    st.header("Extract a Secret Message")
    st.write(
        "Upload a stego audio or video file to recover any hidden text message from "
        "its samples or frames."
    )

    uploaded = st.file_uploader(
        "Upload or replace a suspected STEGO file (audio or video)",
        type=["wav", "mp3", "flac", "ogg", "m4a", "mp4", "avi", "mkv", "mov", "flv"],
        key="file_extract",
    )
    if uploaded is not None:
        update_shared_file(uploaded, max_bytes=MAX_EXTRACT_FILE_BYTES)

    show_shared_file_info()

    kind = st.session_state.get("shared_file_kind")

    video_mode = None
    if kind == "video":
        video_mode = st.radio(
            "For videos: where do you want to extract from?",
            ["Auto (frames + audio track)", "Video frames only", "Audio track only"],
            key="extract_video_mode",
        )

    if st.button("Extract message", use_container_width=True):
        if not has_shared_file():
            st.error("Please upload a stego file first.")
            return

        temp_path, kind, _ = make_temp_file_from_shared()
        if temp_path is None:
            st.error("Internal error: shared file missing.")
            return

        try:
            if kind == "audio":
                st.info("Detected AUDIO file – extracting from audio samples.")
                msg = extract_lsb_audio(temp_path)
                st.subheader("Recovered message")
                st.code(msg or "", language="text")
            elif kind == "video":
                st.info("Detected VIDEO file.")
                # Default when None: auto
                if video_mode is None:
                    mode_label = "Auto (frames + audio track)"
                else:
                    mode_label = video_mode

                if mode_label.startswith("Auto"):
                    if not has_ffmpeg():
                        st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                        return
                    msg_frames = extract_lsb_video(temp_path)
                    msg_audio = extract_message_from_video_audio(temp_path)
                    st.subheader("Recovered from VIDEO FRAMES")
                    st.code(msg_frames or "", language="text")
                    st.subheader("Recovered from AUDIO TRACK")
                    st.code(msg_audio or "", language="text")
                elif mode_label.startswith("Video frames"):
                    if not has_ffmpeg():
                        st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                        return
                    msg_frames = extract_lsb_video(temp_path)
                    st.subheader("Recovered from VIDEO FRAMES")
                    st.code(msg_frames or "", language="text")
                else:  # audio track only
                    if not has_ffmpeg():
                        st.error("Video steganography requires ffmpeg, which was not found on this system. Please install ffmpeg or use audio-only files.")
                        return
                    msg_audio = extract_message_from_video_audio(temp_path)
                    st.subheader("Recovered from AUDIO TRACK")
                    st.code(msg_audio or "", language="text")
            else:
                st.error("Unsupported file type.")
        except Exception as e:
            st.error(f"Error during extraction: {e}")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def show_main_app():
    st.title("StegDetector – Dashboard")
    st.caption("Audio & video steganography toolkit")
    st.markdown(
        "Use this dashboard to **analyze**, **embed**, and **extract** hidden messages "
        "from audio and video files. Choose a tab below to get started."
    )
    st.info(
        "Note: The online Streamlit demo may be slower or have stricter limits on file size. "
        "For the best performance and to test very large files, you can run the local "
        "StegDetector executable on your own machine."
    )
    if not has_ffmpeg():
        st.warning(
            "ffmpeg was not detected on this system. Video-related embedding and extraction may fail. "
            "Audio-only steganography will still work. For full functionality, please install ffmpeg and add it to your PATH."
        )
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    user = st.session_state.get("logged_in_user") or "Unknown user"

    # ----- SIDEBAR LAYOUT -----
    with st.sidebar:
        st.markdown(
            """
            <h2 style="margin-bottom: 0.25rem;">StegDetector</h2>
            <p style="font-size: 0.85rem; color: #6c757d; margin-top: 0;">Audio &amp; video steganography toolkit</p>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown(f"**Logged in as:** `{user}`")

        # Reset session: clear shared file and stego-related state (not authentication)
        if st.button("♻ Reset session", key="reset_session_button"):
            reset_app_state()
            st.rerun()

        # Separate, more "danger-looking" log out
        if st.button("❌ Log out", key="logout_button"):
            st.session_state["logged_in_user"] = None
            st.rerun()

        st.markdown("---")
        with st.expander("ℹ️ Quick help", expanded=False):
            st.write(
                "- **Analyze**: upload a cover or stego file to check for hidden content.\n"
                "- **Embed**: hide a secret message in audio or video using LSB.\n"
                "- **Extract**: recover hidden messages from audio/video stego files.\n"
                "- The same uploaded file is shared across all tabs.\n"
                "- If the online demo feels slow or limited, use the local executable version.\n"
                "- Double embedding (video frames + audio track) produces the largest stego files and may be slower on the online demo."
            )

    # ----- MAIN TABS -----
    tab_analyze, tab_embed, tab_extract = st.tabs(
        ["🧪 Analyze", "🕵️ Embed", "🔍 Extract"]
    )

    with tab_analyze:
        show_analyze_tab()
    with tab_embed:
        show_embed_tab()
    with tab_extract:
        show_extract_tab()

    # Small footer
    st.markdown("---")
    st.caption("StegDetector v1.0 · AUB EECE 632 Cryptography & Network Security project")


# ---------- ENTRYPOINT ----------

def main():
    st.set_page_config(page_title="StegDetector", layout="wide")
    inject_global_styles()
    inject_global_css()
    init_db()
    init_app_state()

    if st.session_state["logged_in_user"] is None:
        show_auth_page()
    else:
        show_main_app()


if __name__ == "__main__":
    main()
