# debug_audio_extract_training.py
from pathlib import Path
from core.stego_audio import extract_lsb_audio

STEGO = Path("data/audio/stego/synthetic_00_stego.wav")
print("Reading from:", STEGO)

msg = extract_lsb_audio(STEGO)
print("Extracted:", repr(msg))
