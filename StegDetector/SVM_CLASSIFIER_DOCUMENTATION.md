# SVM Classifier Documentation

## Overview
The StegDetector project uses **Support Vector Machine (SVM)** classifiers built from scratch (not pretrained) to detect steganographic content in audio and video files.

---

## Audio SVM Classifier

### Training Details
- **Location**: `training/train_audio_svm.py`
- **Model Saved**: `models/audio_svm.joblib`
- **Scaler Saved**: `models/audio_scaler.joblib`

### Feature Extraction
**Features Used**: MFCC (Mel-Frequency Cepstral Coefficients)
- Extracted via `core.audio_detector.extract_audio_features()`
- Standard audio feature set used in speech and audio analysis
- Captures the frequency characteristics of the audio signal

### Training Process
1. **Data Loading**:
   - Cover audio samples from `data/audio/cover/` (label = 0)
   - Stego audio samples from `data/audio/stego/` (label = 1)

2. **Preprocessing**:
   - Features are scaled using `StandardScaler` to normalize feature ranges

3. **Train/Test Split**:
   - 80% training, 20% testing
   - Stratified split to maintain class balance
   - Random seed = 42 for reproducibility

4. **SVM Configuration**:
   ```python
   SVC(
       kernel="rbf",              # Radial Basis Function kernel for non-linear separation
       probability=True,          # Enable probability estimates
       C=10.0,                   # Regularization strength (higher = stricter)
       gamma="scale",            # Kernel coefficient (1 / (n_features * X.var()))
       class_weight="balanced"   # Handle class imbalance
   )
   ```

### Performance
To check the accuracy, you need to:
1. Ensure you have training data in `data/audio/cover/` and `data/audio/stego/`
2. Run: `python training/train_audio_svm.py`
3. The script will output a classification report with:
   - **Precision**: How many detected stego are actually stego
   - **Recall**: How many actual stego samples were detected
   - **F1-Score**: Harmonic mean of precision and recall
   - **Accuracy**: Overall correct predictions

---

## Video SVM Classifier

### Training Details
- **Location**: `training/train_video_svm.py`
- **Model Saved**: `models/video_svm.joblib`
- **Scaler Saved**: `models/video_scaler.joblib`

### Feature Extraction
**Features Used**: Residual Histogram Analysis
- **Method**: Extract residuals between frames and their Gaussian blur
- **Parameters**:
  - Max frames sampled: 40 frames
  - Frame sampling step: every 2nd frame
  - Histogram bins: 32 bins
  - Residual range: [-40, 40] pixel value range

**Rationale**: LSB embedding in video frames alters pixel values slightly. The histogram of residuals (pixel - blurred_pixel) captures these subtle changes that indicate the presence of steganographic content.

### Training Process
1. **Data Loading**:
   - Cover videos from `data/video/cover/` (label = 0)
   - Stego videos from `data/video/stego/` (label = 1)

2. **Feature Computation**:
   - Processes up to 40 frames per video
   - Computes residual histogram for each frame
   - Averages histograms across all frames → final feature vector (32 dimensions)

3. **Preprocessing**:
   - Features are scaled using `StandardScaler`

4. **Train/Test Split**:
   - 80% training, 20% testing
   - Stratified split for balanced classes
   - Random seed = 42 for reproducibility

5. **SVM Configuration**:
   ```python
   SVC(
       kernel="rbf",              # Radial Basis Function kernel
       gamma="scale",            # Automatic gamma calculation
       C=1.0,                    # Moderate regularization
       probability=True,         # Enable probability estimates
       random_state=42           # Reproducibility
   )
   ```

### Performance
To check the accuracy, you need to:
1. Ensure you have training data in `data/video/cover/` and `data/video/stego/`
2. Run: `python training/train_video_svm.py`
3. The script will output a classification report showing precision, recall, F1-score, and accuracy

---

## Built From Scratch vs Pretrained

**Answer**: The SVM classifiers are **BUILT FROM SCRATCH** using scikit-learn's SVC class with custom:
- Feature extraction methods specific to steganalysis
- SVM hyperparameters tuned for steganography detection
- No transfer learning or pretrained models used

### Why Custom Training?
1. **Domain-Specific Features**: Generic audio/video models don't extract steganalysis-relevant features (MFCC for audio, residual histograms for video)
2. **Steganography-Specific Task**: Need models trained on actual cover vs. stego data pairs
3. **Control**: Full control over the detection pipeline

---

## Dataset Information

### Audio Dataset
- **Cover**: Natural/untouched audio files (no steganography)
- **Stego**: Same audio files with LSB-embedded secret messages
- **Location**: `data/audio/cover/` and `data/audio/stego/`
- **Generation**: Created via `training/generate_audio_stego.py`

### Video Dataset
- **Cover**: Natural/untouched video files
- **Stego**: Same video files with LSB-embedded secret messages in pixel values
- **Location**: `data/video/cover/` and `data/video/stego/`
- **Generation**: Created via `training/generate_video_stego.py`

---

## How to Get Accuracy Metrics

### Step 1: Prepare Training Data
```bash
# Generate synthetic stego samples if not already created
python training/generate_audio_stego.py
python training/generate_video_stego.py
```

### Step 2: Train Models
```bash
# Train audio SVM
python training/train_audio_svm.py

# Train video SVM
python training/train_video_svm.py
```

### Step 3: Check Results
The training scripts will print:
- Classification reports with Precision, Recall, F1-Score for each class
- Overall accuracy
- Class distribution in training/test sets

---

## Model Usage in Application

The trained models are used in:
- **Audio Analysis**: `core/audio_detector.py` → `analyze_audio()`
- **Video Analysis**: `core/video_detector.py` → `analyze_video()`

Both load the pre-trained SVM and scaler to classify uploaded files.

---

## Potential Improvements

1. **Ensemble Methods**: Combine multiple classifiers for better accuracy
2. **Deep Learning**: CNNs might capture more complex steganalysis patterns
3. **More Training Data**: Larger datasets improve generalization
4. **Different Embedding Methods**: Train on multiple LSB variants
5. **Cross-Validation**: Use k-fold CV for more robust accuracy estimates

---

## References

- **MFCC Features**: Standard in speech/audio analysis for capturing perceptual frequency characteristics
- **Residual Analysis**: Common steganalysis technique for detecting pixel-value modifications
- **SVM**: Popular classifier in steganalysis research due to good generalization on medium-sized datasets
- **Scikit-learn SVC Documentation**: https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html
