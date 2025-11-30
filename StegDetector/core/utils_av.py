import os
from pathlib import Path
from typing import List, Tuple

import cv2
from moviepy import VideoFileClip

# Silence most OpenCV backend noise (ffmpeg / MSMF warnings)
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    # If you want *zero* messages, you can use:
    # cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except Exception:
    # Older OpenCV versions might not have utils.logging
    pass


AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".flv"}


def is_audio_file(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in AUDIO_EXTENSIONS


def is_video_file(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def extract_audio_from_video(video_path: str, output_wav_path: str) -> str:
    """
    Extract audio track from video and save as WAV.
    Returns the path to the WAV file.
    """
    video_path = str(video_path)
    output_wav_path = str(output_wav_path)
    clip = VideoFileClip(video_path)
    if clip.audio is None:
        raise ValueError("Video has no audio track.")
    clip.audio.write_audiofile(output_wav_path, codec="pcm_s16le")
    clip.close()
    return output_wav_path


def extract_frames(video_path: str, max_frames: int = 50, frame_step: int = 5) -> list:
    """
    Extract up to `max_frames` frames from a video.

    1) First try OpenCV (fast, what we used in training).
    2) If OpenCV fails or returns zero frames (e.g. unsupported codec),
       fall back to MoviePy + ffmpeg.
    """

    video_path = str(video_path)
    frames: list = []

    # --- Small optimisation: for .mkv (our stego containers) go straight to MoviePy ---
    if Path(video_path).suffix.lower() == ".mkv":
        return _extract_frames_moviepy(video_path, max_frames)

    # -------------------- Try OpenCV first --------------------
    cap = cv2.VideoCapture(video_path)
    if cap.isOpened():
        frame_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_index % frame_step == 0:
                frames.append(frame)
                if len(frames) >= max_frames:
                    break

            frame_index += 1

        cap.release()

    if frames:
        return frames

    # -------------------- Fallback: MoviePy --------------------
    return _extract_frames_moviepy(video_path, max_frames)


def _extract_frames_moviepy(video_path: str, max_frames: int) -> list:
    """Fallback frame extraction using MoviePy (for unsupported codecs)."""
    frames = []
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration or 0.0
        if duration <= 0:
            clip.close()
            return []

        num_samples = max_frames
        times = [duration * (i + 0.5) / num_samples for i in range(num_samples)]

        for t in times:
            try:
                frame_rgb = clip.get_frame(t)
            except Exception:
                continue

            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            frames.append(frame_bgr)
            if len(frames) >= max_frames:
                break
        clip.close()
    except Exception as e:
        print(f"[extract_frames] MoviePy fallback failed for {video_path}: {e}")

    return frames


def ensure_dir(path: str) -> None:
    """
    Create directory if it does not exist.
    """
    os.makedirs(path, exist_ok=True)
