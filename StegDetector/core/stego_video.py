# core/stego_video.py
from __future__ import annotations

from pathlib import Path
from typing import Union, List

import numpy as np
import imageio.v2 as imageio

PathLike = Union[str, Path]

HEADER_BYTES = 4  # store length as 32-bit big-endian


def _encode_message_to_bits(message: str) -> np.ndarray:
    """
    Encode message as: [4-byte length header][UTF-8 bytes] -> bit array of 0/1.
    """
    msg_bytes = message.encode("utf-8")
    length = len(msg_bytes)

    header = length.to_bytes(HEADER_BYTES, byteorder="big")
    payload = header + msg_bytes

    bit_list = []
    for b in payload:
        for i in range(7, -1, -1):
            bit_list.append((b >> i) & 1)

    bits = np.array(bit_list, dtype=np.uint8)
    return bits


def _decode_bits_to_message(bits: np.ndarray, max_len_bytes: int = 200_000) -> str | None:
    """
    Inverse of _encode_message_to_bits.
    Returns None if header looks impossible or message is empty.
    """
    bits = bits.astype(np.uint8).flatten()
    if bits.size < HEADER_BYTES * 8:
        return None

    # First 32 bits -> 4-byte length
    length_bits = bits[: HEADER_BYTES * 8]
    length_val = 0
    for b in length_bits:
        length_val = (length_val << 1) | int(b)

    max_possible = (bits.size - HEADER_BYTES * 8) // 8
    if length_val <= 0 or length_val > max_possible or length_val > max_len_bytes:
        return None

    needed = HEADER_BYTES * 8 + length_val * 8
    if bits.size < needed:
        return None

    msg_bits = bits[HEADER_BYTES * 8 : needed].reshape(-1, 8)
    byte_vals: List[int] = []
    for byte in msg_bits:
        val = 0
        for b in byte:
            val = (val << 1) | int(b)
        byte_vals.append(val)

    try:
        msg = bytes(byte_vals).decode("utf-8", errors="replace")
    except Exception:
        return None

    if msg.strip() == "":
        return None
    return msg


def embed_lsb_video(cover_path: PathLike, stego_path: PathLike, message: str) -> None:
    """
    Embed a UTF-8 text message into the LSBs of a video.

    Uses ffmpeg to work directly with video frames without color space conversion.
    """
    from shutil import which
    import subprocess
    import tempfile
    import shutil
    
    cover_path = Path(cover_path)
    stego_path = Path(stego_path)
    stego_path.parent.mkdir(parents=True, exist_ok=True)

    if which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required but not found in PATH.")

    # Get video info
    reader = imageio.get_reader(str(cover_path))
    meta = reader.get_meta_data()
    fps = meta.get("fps", 25)
    reader.close()

    # Create temp directory for frame files
    temp_dir = Path(tempfile.gettempdir()) / "steg_video_frames"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract frames using ffmpeg (preserves YUV colorspace)
        frame_pattern = str(temp_dir / "frame_%06d.png")
        extract_cmd = [
            "ffmpeg", "-i", str(cover_path),
            "-pix_fmt", "rgb24",  # Convert to RGB for LSB embedding
            frame_pattern
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg extraction failed: {result.stderr}")

        # Get all frame files
        frame_files = sorted(temp_dir.glob("frame_*.png"))
        if not frame_files:
            raise RuntimeError("No frames extracted from video")

        # Read all frames and flatten
        frames: List[np.ndarray] = []
        for frame_file in frame_files:
            frame = imageio.imread(str(frame_file)).astype(np.uint8)
            frames.append(frame)

        # Flatten all frames
        flat = np.concatenate([f.reshape(-1) for f in frames]).astype(np.uint8)
        capacity = flat.size

        # Encode and embed message
        bits = _encode_message_to_bits(message)
        if bits.size > capacity:
            raise ValueError(
                f"Video too small for message. Capacity bits={capacity}, needed={bits.size}"
            )

        # Embed bits into LSBs
        for i in range(bits.size):
            if bits[i]:
                flat[i] = flat[i] | 0x01
            else:
                flat[i] = flat[i] & 0xFE

        # Reshape back into frames
        idx = 0
        for i in range(len(frames)):
            size = frames[i].size
            frames[i] = flat[idx : idx + size].reshape(frames[i].shape).astype(np.uint8)
            idx += size

        # Write frames back as PNG
        for i, frame in enumerate(frames):
            frame_file = temp_dir / f"frame_{i+1:06d}.png"
            imageio.imwrite(str(frame_file), frame)

        # Encode video using ffmpeg with FFV1
        output_pattern = str(temp_dir / "frame_%06d.png")
        encode_cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", output_pattern,
            "-c:v", "ffv1",
            "-level", "3",
            str(stego_path)
        ]

        result = subprocess.run(encode_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg encoding failed: {result.stderr}")

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def extract_lsb_video(stego_path: PathLike) -> str:
    """
    Extract a message from LSBs of a video created by embed_lsb_video.

    For arbitrary external videos, header may be invalid and we return
    a clear message instead of garbage.
    """
    stego_path = Path(stego_path)

    try:
        reader = imageio.get_reader(str(stego_path))
    except Exception as e:
        return f"[Failed to open video: {e}]"
    
    bits_list: List[np.ndarray] = []

    try:
        for frame_idx, frame in enumerate(reader):
            frame = frame.astype(np.uint8)
            flat = frame.reshape(-1)
            frame_bits = flat & 1
            bits_list.append(frame_bits)
    except Exception as e:
        return f"[Error reading frames: {e}]"
    finally:
        reader.close()

    if not bits_list:
        return "[No frames found in this video]"

    bits = np.concatenate(bits_list)
    
    # Debug: print bit statistics
    # print(f"Total bits extracted: {bits.size}, header bits: {bits[:32]}")
    
    msg = _decode_bits_to_message(bits)
    if msg is None:
        return "[No valid LSB text payload found in this video]"
    return msg
