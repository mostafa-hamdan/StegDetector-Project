# debug_audio_stego.py
from pathlib import Path

from core.stego_audio import embed_lsb_audio, extract_lsb_audio

COVER = Path("data/audio/cover/synthetic_00.wav")
STEGO = Path("data/audio/cover/synthetic_00_manual_stego.wav")
MSG = "MANUAL TEST MESSAGE 123"

print("Cover:", COVER)
print("Stego:", STEGO)

embed_lsb_audio(COVER, STEGO, MSG)
print("Embedded message into:", STEGO)

decoded = extract_lsb_audio(STEGO)
print("Decoded message:", decoded)
