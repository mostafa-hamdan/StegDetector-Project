from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import cv2
import imageio.v2 as imageio 
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
import joblib

from .utils_av import extract_frames


MODELS_DIR = Path("models")
VIDEO_SCALER_PATH = MODELS_DIR / "video_scaler.joblib"
VIDEO_SVM_PATH = MODELS_DIR / "video_svm.joblib"


# ========================
# V1: Frame-based LSB Detector
# ========================

def frame_lsb_statistics(frames: List[np.ndarray]) -> Dict[str, Any]:
    """
    Compute simple LSB stats over a list of frames (BGR images).
    """
    if not frames:
        return {
            "method": "V1_frame_LSB_stats",
            "score": 0.0,
            "verdict": "No frames extracted"
        }

    all_lsb = []
    for frame in frames:
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lsb = gray & 1
        all_lsb.append(lsb.flatten())

    all_lsb = np.concatenate(all_lsb)
    ones = np.count_nonzero(all_lsb)
    zeros = all_lsb.size - ones
    p1 = ones / float(all_lsb.size)
    p0 = zeros / float(all_lsb.size)

    balance = 1.0 - abs(p1 - 0.5) * 2.0  # in [0,1]

    if balance < 0.4:
        verdict = "Likely clean (LSB distribution skewed)"
    elif balance < 0.7:
        verdict = "Uncertain (LSB distribution moderate)"
    else:
        verdict = "Suspicious (LSB distribution very balanced)"

    return {
        "method": "V1_frame_LSB_stats",
        "score": float(balance),
        "p0": float(p0),
        "p1": float(p1),
        "verdict": verdict
    }


# ========================
# V2: Frame residual features + SVM (Best Video Method)
# ========================

def extract_video_features(
    path: str | Path,
    max_frames: int = 40,
    frame_step: int = 2,
    bins: int = 32,
) -> np.ndarray:
    """
    Extract residual-based histogram features from a video.

    This MUST match the feature extraction used in training/train_video_svm.py:

      - Read up to `max_frames` frames using imageio (ffmpeg backend).
      - Convert each frame to grayscale.
      - Apply Gaussian blur and compute residual = gray - blur.
      - Build a histogram of residual values in [-40, 40] with `bins` bins.
      - Average histograms over frames => final feature vector of length `bins`.
    """
    path = Path(path)

    # imageio reader uses ffmpeg under the hood (better codec support)
    reader = imageio.get_reader(str(path))
    frames: List[np.ndarray] = []

    # Sample every `frame_step`-th frame, up to `max_frames`
    for idx, frame in enumerate(reader):
        if idx % frame_step != 0:
            continue
        frames.append(frame.astype(np.uint8))
        if len(frames) >= max_frames:
            break

    reader.close()

    if not frames:
        raise ValueError("No frames extracted from video.")

    feats_per_frame: List[np.ndarray] = []

    for frame in frames:
        # imageio returns RGB frames
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        resid = gray.astype(np.int16) - blurred.astype(np.int16)

        hist, _ = np.histogram(
            resid,
            bins=bins,
            range=(-40, 40),
            density=True,
        )
        feats_per_frame.append(hist.astype(np.float32))

    feats = np.stack(feats_per_frame, axis=0)   # (n_frames, bins)
    feat_mean = feats.mean(axis=0)              # (bins,)

    return feat_mean



def video_frame_svm(path: str) -> Dict[str, Any]:
    """
    Run frame-feature+SVM model on video.

    If the scaler/model are missing OR incompatible with the current
    feature vector (dimension mismatch etc.), this returns a result with
    score=None and a descriptive verdict, so that the GUI doesn't crash.

    In that case, V1 (frame LSB statistics) is still used normally.
    """
    method_name = "V2_frame_SVM"

    # 1) Check that model files exist
    if not VIDEO_SCALER_PATH.exists() or not VIDEO_SVM_PATH.exists():
        return {
            "method": method_name,
            "score": None,
            "verdict": "Model not trained yet. Run training/train_video_svm.py.",
        }

    # 2) Load scaler + SVM
    try:
        scaler: StandardScaler = joblib.load(VIDEO_SCALER_PATH)
        clf: SVC = joblib.load(VIDEO_SVM_PATH)
    except Exception as e:
        return {
            "method": method_name,
            "score": None,
            "verdict": f"Could not load video SVM model: {e}",
        }

    # 3) Extract features
    try:
        feats = extract_video_features(path)  # 1D vector
    except Exception as e:
        return {
            "method": method_name,
            "score": None,
            "verdict": f"Feature extraction failed: {e}",
        }

    # 4) Scale features – this is where the dimension mismatch happened
    try:
        feats_scaled = scaler.transform([feats])  # shape (1, n_features)
    except Exception as e:
        n_feats = int(getattr(feats, "shape", [len(feats)])[0])
        return {
            "method": method_name,
            "score": None,
            "verdict": (
                "Video SVM model is not compatible with the current feature vector "
                f"(got {n_feats} features; scaler expects {getattr(scaler, 'n_features_in_', 'unknown')}). "
                "You likely changed extract_video_features() after training. "
                "Re-run training/train_video_svm.py with the current features "
                "if you want V2 to work, or ignore this message and rely on V1."
                f"\nInternal error: {e}"
            ),
        }

    # 5) Predict probability of stego
    try:
        if hasattr(clf, "predict_proba"):
            proba = float(clf.predict_proba(feats_scaled)[0, 1])
        else:
            # Fallback: use decision_function and squash with sigmoid
            dec = float(clf.decision_function(feats_scaled)[0])
            proba = 1.0 / (1.0 + np.exp(-dec))
    except Exception as e:
        return {
            "method": method_name,
            "score": None,
            "verdict": f"Video SVM prediction failed: {e}",
        }

    # 6) Map probability -> human-readable verdict
    if proba < 0.4:
        verdict = "Likely clean"
    elif proba < 0.6:
        verdict = "Uncertain"
    else:
        verdict = "Likely stego"

    return {
        "method": method_name,
        "score": proba,
        "verdict": verdict,
    }



def analyze_video(path: str) -> Dict[str, Any]:
    """
    Run all video detectors and return a combined result.
    """
    path = str(path)

    # Extract frames once for V1
    frames = extract_frames(path, frame_step=10, max_frames=200)
    v1_result = frame_lsb_statistics(frames)
    v2_result = video_frame_svm(path)

    results = [v1_result, v2_result]

    best_video_score = None
    best_method = None
    for r in results:
        if r.get("score") is None:
            continue
        if best_video_score is None or r["score"] > best_video_score:
            best_video_score = r["score"]
            best_method = r["method"]

    overview = {
        "best_score": best_video_score,
        "best_method": best_method,
        "methods": results,
    }

    return overview
