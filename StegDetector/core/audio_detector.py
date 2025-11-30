from pathlib import Path
from typing import Dict, Any

import numpy as np
import librosa
import soundfile as sf
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
import joblib
import os


MODELS_DIR = Path("models")
AUDIO_SCALER_PATH = MODELS_DIR / "audio_scaler.joblib"
AUDIO_SVM_PATH = MODELS_DIR / "audio_svm.joblib"


# ========================
# A1: LSB Statistical Audio Detector
# ========================

def _load_audio_pcm16(path: str) -> np.ndarray:
    """
    Load audio as 16-bit PCM samples (mono).
    """
    y, sr = librosa.load(path, sr=None, mono=True)
    # Scale float [-1, 1] to int16
    pcm = np.clip(y * 32767.0, -32768, 32767).astype(np.int16)
    return pcm


def audio_lsb_statistics(path: str) -> Dict[str, Any]:
    """
    Simple LSB-based detector.
    Computes the proportion of 0 and 1 in the LSBs and returns a suspicion score.

    Idea: natural audio does not always have perfectly balanced LSBs.
    Strongly stego-modified audio often pushes distribution closer to 0.5.
    We treat "too close to 0.5" as suspicious.
    """
    pcm = _load_audio_pcm16(path)
    if pcm.size == 0:
        return {
            "method": "A1_LSB_stats",
            "score": 0.0,
            "verdict": "Audio too short / invalid"
        }

    lsb = pcm & 1
    ones = np.count_nonzero(lsb)
    zeros = lsb.size - ones
    p1 = ones / float(lsb.size)
    p0 = zeros / float(lsb.size)

    # Suspicion: 1 when perfectly balanced (0.5 / 0.5), 0 when fully skewed.
    balance = 1.0 - abs(p1 - 0.5) * 2.0  # in [0,1]

    # Heuristic verdicts
    if balance < 0.4:
        verdict = "Likely clean (LSB distribution skewed)"
    elif balance < 0.7:
        verdict = "Uncertain (LSB distribution moderate)"
    else:
        verdict = "Suspicious (LSB distribution very balanced)"

    return {
        "method": "A1_LSB_stats",
        "score": float(balance),
        "p0": float(p0),
        "p1": float(p1),
        "verdict": verdict
    }


# ========================
# A2: MFCC + SVM (Best Audio Method)
# ========================

def extract_audio_features(path: str, sr: int = 16000) -> np.ndarray:
    """
    Extract MFCC + basic spectral features from an audio file.
    This must match the features used during training.
    """
    y, _ = librosa.load(path, sr=sr, mono=True)
    if y.size == 0:
        raise ValueError("Empty audio signal.")

    # Trim or pad to reasonable length (optional)
    # Here we just keep as-is.

    # MFCCs
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = mfcc.mean(axis=1)
    mfcc_std = mfcc.std(axis=1)

    # Spectral features
    spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    spec_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    spec_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)

    features = np.concatenate([
        mfcc_mean,
        mfcc_std,
        spec_centroid.mean(axis=1),
        spec_bandwidth.mean(axis=1),
        spec_rolloff.mean(axis=1),
        zcr.mean(axis=1),
    ])

    return features.astype(np.float32)


def audio_mfcc_svm(path: str) -> Dict[str, Any]:
    """
    Run MFCC+SVM model on audio.
    Requires that training/train_audio_svm.py was executed to create model files.
    """
    if not AUDIO_SCALER_PATH.exists() or not AUDIO_SVM_PATH.exists():
        return {
            "method": "A2_MFCC_SVM",
            "score": None,
            "verdict": "Model not trained yet. Run training/train_audio_svm.py.",
        }

    scaler: StandardScaler = joblib.load(AUDIO_SCALER_PATH)
    clf: SVC = joblib.load(AUDIO_SVM_PATH)

    feats = extract_audio_features(path)
    feats_scaled = scaler.transform([feats])
    proba = clf.predict_proba(feats_scaled)[0, 1]  # probability of stego class

    if proba < 0.3:
        verdict = "Likely clean"
    elif proba < 0.7:
        verdict = "Uncertain"
    else:
        verdict = "Likely stego"

    return {
        "method": "A2_MFCC_SVM",
        "score": float(proba),
        "verdict": verdict
    }


def analyze_audio(path: str) -> Dict[str, Any]:
    """
    Run all audio detectors and return a combined result.
    """
    path = str(path)
    results = []

    # A1 always available
    results.append(audio_lsb_statistics(path))

    # A2 if model exists
    results.append(audio_mfcc_svm(path))

    # Combine into overview (simple heuristic: max score when available)
    best_audio_score = None
    best_method = None
    for r in results:
        if r.get("score") is None:
            continue
        if best_audio_score is None or r["score"] > best_audio_score:
            best_audio_score = r["score"]
            best_method = r["method"]

    overview = {
        "best_score": best_audio_score,
        "best_method": best_method,
        "methods": results,
    }

    return overview
