# core/stego_audio.py
from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import soundfile as sf

PathLike = Union[str, Path]


def _encode_message_to_bits(message: str) -> np.ndarray:
    """
    Encode message as: [4-byte length header][UTF-8 bytes] -> bit array of 0/1.
    """
    msg_bytes = message.encode("utf-8")
    length = len(msg_bytes)

    # 4-byte big-endian length header
    header = length.to_bytes(4, byteorder="big")
    payload = header + msg_bytes

    bit_str = "".join(f"{b:08b}" for b in payload)
    bits = np.fromiter((int(ch) for ch in bit_str), dtype=np.uint8)
    return bits


def _decode_bits_to_message(bits: np.ndarray, max_len_bytes: int = 100_000) -> str | None:
    """
    Inverse of _encode_message_to_bits.
    Returns None if header looks impossible or message is empty.
    """
    bits = bits.astype(np.uint8).flatten()
    if bits.size < 32:
        return None

    # First 32 bits -> 4-byte length
    length_bits = bits[:32]
    length_val = 0
    for b in length_bits:
        length_val = (length_val << 1) | int(b)

    # Sanity checks
    max_possible = (bits.size - 32) // 8
    if length_val <= 0 or length_val > max_possible or length_val > max_len_bytes:
        return None

    needed = 32 + length_val * 8
    if bits.size < needed:
        return None

    msg_bits = bits[32:needed].reshape(-1, 8)
    byte_vals = []
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


def _load_audio_int16(path: PathLike) -> tuple[np.ndarray, int]:
    """
    Load audio directly as int16 PCM.
    Works for mono or multi-channel WAV/PCM files.
    Shape: (samples, channels)
    """
    data, sr = sf.read(str(path), dtype="int16", always_2d=True)
    data = np.asarray(data, dtype=np.int16)
    return data, sr


def _save_audio_int16(path: PathLike, int_data: np.ndarray, sr: int) -> None:
    """
    Save int16 PCM directly to disk (no manual scaling).
    """
    int_data = np.asarray(int_data, dtype=np.int16)
    sf.write(str(path), int_data, sr, subtype="PCM_16")


def embed_lsb_audio(cover_path: PathLike, stego_path: PathLike, message: str) -> None:
    """
    Embed a UTF-8 text message into the LSBs of an audio file.
    Output is written as WAV at stego_path.

    Capacity = num_samples * num_channels  (1 bit per sample).
    """
    cover_path = Path(cover_path)
    stego_path = Path(stego_path)
    stego_path.parent.mkdir(parents=True, exist_ok=True)

    int_data, sr = _load_audio_int16(cover_path)
    shape = int_data.shape  # (samples, channels)

    # Work in int32 to avoid any overflow issues with bitwise ops
    flat32 = int_data.reshape(-1).astype(np.int32)

    bits = _encode_message_to_bits(message).astype(np.int32)
    capacity = flat32.size

    if bits.size > capacity:
        raise ValueError(
            f"Message too long for this audio. "
            f"Capacity bits = {capacity}, needed = {bits.size}"
        )

    # Clear + set LSBs in the first bits.size samples
    flat32[:bits.size] = (flat32[:bits.size] & ~1) | bits

    stego_int16 = flat32.reshape(shape).astype(np.int16)
    _save_audio_int16(stego_path, stego_int16, sr)


def extract_lsb_audio(stego_path: PathLike) -> str:
    """
    Try to extract a message from LSBs of an audio file created by embed_lsb_audio.
    If no plausible header is found, returns a friendly message instead of garbage.
    """
    int_data, sr = _load_audio_int16(stego_path)
    flat32 = int_data.reshape(-1).astype(np.int32)
    bits = (flat32 & 1).astype(np.uint8)

    msg = _decode_bits_to_message(bits)
    if msg is None:
        return "[No valid LSB text payload found in this audio file]"
    return msg
