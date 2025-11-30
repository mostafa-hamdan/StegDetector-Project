# debug_video_stego.py
from pathlib import Path
from core.stego_video import embed_lsb_video, extract_lsb_video

COVER = Path("data/video/cover/synthetic_00.mp4")
STEGO = Path("data/video/cover/synthetic_00_manual_stego.avi")
MSG = "MANUAL VIDEO TEST 123"

print("Cover:", COVER)
print("Stego:", STEGO)

embed_lsb_video(COVER, STEGO, MSG)
print("Embedded message into:", STEGO)

decoded = extract_lsb_video(STEGO)
print("Decoded message:", decoded)
