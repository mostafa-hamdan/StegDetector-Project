# StegDetector - Complete Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Technical Stack](#technical-stack)
5. [Project Structure](#project-structure)
6. [Core Modules](#core-modules)
7. [Key Modifications](#key-modifications)
8. [Installation & Setup](#installation--setup)
9. [Usage Guide](#usage-guide)
10. [SVM Classifiers](#svm-classifiers)
11. [Development Notes](#development-notes)

---

## Project Overview

**StegDetector** is a comprehensive steganography detection and embedding system for both audio and video files. It's built as a secure web application using Streamlit, allowing users to:
- **Embed** secret messages in audio/video files using LSB (Least Significant Bit) steganography
- **Extract** hidden messages from stego files
- **Analyze** files for the presence of steganographic content using trained SVM classifiers

### Purpose
This is an educational project for EECE 632 (Cryptography and Network Security) course, demonstrating practical implementation of steganography techniques and detection methods.

### Key Concepts
- **LSB Steganography**: Embeds data in the least significant bits of media samples/pixels
- **Steganalysis**: Detects the presence of hidden information using machine learning
- **Audio Stego**: Embeds messages in audio sample LSBs using PCM format
- **Video Stego**: Embeds messages in video frame pixel LSBs
- **Multi-format Support**: Handles various audio (WAV, MP3, FLAC, OGG) and video formats (MP4, AVI, MKV, MOV)

---

## Architecture

### High-Level System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Web Interface                  │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │   Analyze    │    Embed     │       Extract            │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    ┌─────────────┐      ┌──────────────┐
    │   Audio     │      │   Video      │
    │  Processing │      │  Processing  │
    └─────────────┘      └──────────────┘
         │                      │
    ┌────▼──────┐       ┌───────▼───────┐
    │ Embedding │       │  Embedding    │
    │ Extraction│       │  Extraction   │
    │ Analysis  │       │  Analysis     │
    └───────────┘       └───────────────┘
         │                      │
    ┌────▼──────┐       ┌───────▼───────┐
    │SVM Audio  │       │ SVM Video     │
    │ Classifier│       │ Classifier    │
    └───────────┘       └───────────────┘
```

### Component Layers

1. **Presentation Layer**: Streamlit UI with 3 main tabs (Analyze, Embed, Extract)
2. **Authentication Layer**: User login/signup with bcrypt password hashing
3. **Processing Layer**: Audio and video steganography modules
4. **Detection Layer**: SVM-based steganalysis classifiers
5. **Data Layer**: SQLite database for user credentials, joblib-serialized models

---

## Features

### 1. **User Authentication**
- **Sign Up**: Create new accounts with password validation
  - Requirements: Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special character
  - Auto-login after successful signup (modification made)
- **Login**: Secure authentication using bcrypt hashing
- **Logout**: Session management across the app

### 2. **Analyze Tab**
- **Upload**: Supports audio and video files
- **Detection**: Runs SVM classifier to detect steganographic content
- **Results**: Returns classification confidence scores
  - Audio: MFCC-based detection with RBF SVM
  - Video: Residual histogram-based detection with RBF SVM
- **File Sharing**: Once uploaded, file is shared across all tabs

### 3. **Embed Tab (Steganography)**

#### Audio Embedding
- **LSB Technique**: Embeds message bits into audio sample LSBs
- **Input**: Audio file + secret message
- **Output**: Stego audio file (same format as input)
- **Preservation**: Audio quality preserved; LSBs modified with message

#### Video Embedding - Three Modes
1. **Video Frames Only**
   - Embeds message in video frame pixel LSBs
   - Does NOT modify audio track
   - Output format: MKV with FFV1 lossless codec

2. **Audio Track Only**
   - Extracts audio from video
   - Embeds message in audio LSBs
   - Re-muxes audio back with original video
   - Output format: MKV with FFV1 video + FLAC audio

3. **Both Frames + Audio** (NEW FEATURE)
   - Option to use same message for both or different messages
   - Embeds one message in video frames, another in audio
   - Output: Single MKV file containing both stegos
   - UI: Checkbox to toggle between single/dual message input

### 4. **Extract Tab**
- **Auto-Detection**: Automatically detects file type (audio/video)
- **Video Extraction Modes**:
  - Auto (extracts from frames AND audio)
  - Video frames only
  - Audio track only
- **Message Recovery**: Reconstructs hidden message from LSBs
- **Error Handling**: Clear messages if no stego found

### 5. **File Management**
- **Shared File State**: Upload once, use across all tabs
- **Clear Button**: Reset uploaded file with one click
- **Temp File Cleanup**: Automatic cleanup of temporary files
- **Format Support**:
  - Audio: WAV, MP3, FLAC, OGG, M4A
  - Video: MP4, AVI, MKV, MOV, FLV

---

## Key Modifications (From Initial Requirements)

### Modification 1: Auto-Login After Signup
**Problem**: Users had to re-enter credentials after signup to login
**Solution**: Added automatic session state update and page rerun after successful account creation
**Code Location**: `streamlit_app.py`, `show_auth_page()` function
```python
if success:
    st.session_state["logged_in_user"] = signup_username
    st.rerun()
```

### Modification 2: Fixed Video File Size Explosion
**Problem**: Embedded videos were 500MB+ from 9MB originals
**Root Cause**: Using PNG codec (uncompressed) for video encoding
**Solution**: 
- Changed to FFV1 codec (lossless but compressed)
- Uses ffmpeg for frame extraction/encoding (prevents color space loss)
- File size now: ~9-150MB (reasonable for lossless preservation)

### Modification 3: Fixed Video Stego Extraction Failure
**Problem**: Extracted video stego returned "No valid LSB text payload found"
**Root Cause**: YUV420p → RGB → YUV420p color space conversion destroyed LSBs
**Solution**:
- Use ffmpeg to extract frames as PNG (lossless, RGB format)
- Embed LSBs in consistent RGB space
- Re-encode with FFV1 (lossless)
- Extraction reads frames same way (consistent color space)

### Modification 4: Added Dual-Message Embedding for Videos
**Problem**: Users could only embed same message in both video+audio
**Solution**: Added checkbox option for dual separate messages
- "Use same message": Single text box for both streams
- "Different messages": Two side-by-side text boxes
- Code Location: `show_embed_tab()` function

### Modification 5: Fixed ffmpeg Muxing Issues
**Problem**: Audio/video muxing failed with timestamp errors
**Solutions Applied**:
- Changed audio codec to FLAC (lossless, better container support)
- Added `-shortest` flag to handle stream length differences
- Use MKV container (native support for FFV1 + FLAC)

### Modification 6: Fixed Duplicate Element Key Errors
**Problem**: "Clear file" button created duplicate keys across tabs
**Solution**: Made button key unique per tab by passing tab identifier
```python
show_shared_file_info("analyze")  # Unique keys for each tab
show_shared_file_info("embed")
show_shared_file_info("extract")
```

---

## Technical Stack

### Frontend
- **Streamlit**: Web framework for interactive UI
- **Python**: Primary programming language

### Backend
- **NumPy**: Numerical operations and array manipulation
- **SciPy**: Scientific computing
- **Scikit-learn**: Machine learning (SVM classifiers)
- **Librosa**: Audio feature extraction (MFCC)
- **OpenCV**: Image processing
- **MoviePy**: Video manipulation (legacy)

### Multimedia Processing
- **imageio**: Frame reading/writing
- **soundfile**: Audio file I/O (WAV, FLAC, etc.)
- **ffmpeg**: Advanced video/audio encoding (via subprocess)

### Data & Models
- **joblib**: Model serialization (SVM classifiers and scalers)
- **SQLite** (via auth_db.py): User credential storage
- **bcrypt**: Password hashing

### Development
- **Python 3.10+**
- **Virtual Environment**: `venv`

---

## Project Structure

```
StegDetector/
├── streamlit_app.py                 # Main Streamlit application
├── auth_db.py                       # SQLite user authentication
├── main.py                          # CLI entry point
├── requirements.txt                 # Python dependencies
│
├── app/                             # GUI components (PyQt5, legacy)
│   ├── __init__.py
│   └── gui/
│       ├── main_window.py
│       └── __pycache__/
│
├── core/                            # Core processing modules
│   ├── __init__.py
│   ├── audio_detector.py            # Audio steganalysis (SVM)
│   ├── video_detector.py            # Video steganalysis (SVM)
│   ├── stego_audio.py               # Audio LSB embedding/extraction
│   ├── stego_video.py               # Video LSB embedding/extraction
│   ├── utils_av.py                  # Utility functions
│   └── __pycache__/
│
├── training/                        # Model training scripts
│   ├── __init__.py
│   ├── train_audio_svm.py           # Train audio SVM classifier
│   ├── train_video_svm.py           # Train video SVM classifier
│   ├── generate_audio_stego.py      # Generate audio training data
│   ├── generate_video_stego.py      # Generate video training data
│   ├── create_synthetic_audio_covers.py
│   ├── create_synthetic_video_covers.py
│   ├── create_demo_video_with_audio.py
│   └── __pycache__/
│
├── models/                          # Trained ML models
│   ├── audio_scaler.joblib          # Audio feature scaler
│   ├── audio_svm.joblib             # Audio SVM classifier
│   ├── video_scaler.joblib          # Video feature scaler
│   └── video_svm.joblib             # Video SVM classifier
│
├── data/                            # Training datasets
│   ├── audio/
│   │   ├── cover/                   # Original audio files
│   │   └── stego/                   # Audio with embedded messages
│   └── video/
│       ├── cover/                   # Original video files
│       └── stego/                   # Video with embedded messages
│
├── demo_data/                       # Demo/test files
│   ├── audio/
│   │   ├── cover/
│   │   └── stego/
│   └── video/
│       ├── cover/
│       └── stego/
│
├── temp/                            # Temporary files (runtime)
│
└── .streamlit/
    └── config.toml                  # Streamlit configuration
        (maxUploadSize = 1024 MB)
```

---

## Core Modules

### 1. **streamlit_app.py** - Main Application

#### Functions
- `classify_file_type()`: Detects audio vs video based on extension
- `init_app_state()`: Initializes session state for file sharing
- `update_shared_file()`: Updates shared file across tabs
- `show_shared_file_info()`: Displays current file info with clear button
- `_mux_video_and_audio()`: Combines video+audio using ffmpeg
- `embed_video_frames_only()`: Embeds in video frames only
- `embed_video_audio_only()`: Embeds in audio track only
- `embed_video_both()`: Embeds in both with separate messages
- `extract_message_from_video_audio()`: Extracts from video's audio track
- `show_auth_page()`: Login/Signup UI
- `show_analyze_tab()`: File analysis tab
- `show_embed_tab()`: Message embedding tab
- `show_extract_tab()`: Message extraction tab
- `show_main_app()`: Main dashboard with 3 tabs
- `main()`: Streamlit app entry point

#### Key Features
- Session-based file sharing across tabs
- Role-based UI (auth page vs main app)
- Error handling with user-friendly messages
- Progress indicators during embedding/extraction

### 2. **auth_db.py** - Authentication

#### Functions
- `init_db()`: Creates SQLite database for users
- `create_user()`: Registers new user with bcrypt hashing
- `verify_user()`: Authenticates user credentials
- `hash_password()`: Bcrypt password hashing
- `check_password()`: Bcrypt password verification

#### Database Schema
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
)
```

### 3. **stego_audio.py** - Audio Steganography

#### Functions
- `_encode_message_to_bits()`: Converts message to bit array with length header
- `_decode_bits_to_message()`: Reconstructs message from bits
- `embed_lsb_audio()`: Embeds message in audio sample LSBs
  - Reads audio with soundfile
  - Embeds bits using bitwise operations
  - Writes stego audio
- `extract_lsb_audio()`: Extracts message from audio
  - Reads stego audio
  - Extracts LSBs
  - Decodes message with error handling

#### Message Format
```
[4 bytes: Length in big-endian] [N bytes: UTF-8 message] [LSB bits embedded]
```

### 4. **stego_video.py** - Video Steganography

#### Functions
- `_encode_message_to_bits()`: Converts message to bit array
- `_decode_bits_to_message()`: Reconstructs message from bits
- `embed_lsb_video()`: Embeds message in video frame pixel LSBs
  - Uses ffmpeg to extract frames as PNG (lossless, consistent RGB)
  - Flattens all frames into single array
  - Embeds bits using bitwise operations
  - Re-encodes with FFV1 codec (lossless)
- `extract_lsb_video()`: Extracts message from video
  - Reads video frames with error handling
  - Extracts LSBs from all frames
  - Decodes message

#### Color Space Handling
- Extracts frames as PNG (RGB24 format)
- Works in RGB space to avoid YUV420p conversion issues
- FFV1 codec preserves all pixel values exactly

### 5. **audio_detector.py** - Audio Steganalysis

#### Functions
- `extract_audio_features()`: Extracts MFCC features from audio
  - Uses librosa to compute MFCC
  - Returns feature vector for classification
- `analyze_audio()`: Classifies audio as cover or stego
  - Loads pretrained SVM and scaler
  - Extracts features
  - Returns classification result with confidence

#### SVM Details
- **Kernel**: RBF (Radial Basis Function)
- **C**: 10.0 (regularization strength)
- **Class Weights**: Balanced
- **Input Features**: MFCC coefficients

### 6. **video_detector.py** - Video Steganalysis

#### Functions
- `extract_video_features()`: Extracts residual histogram features
  - Samples frames with step size
  - Computes Gaussian blur residuals
  - Creates histogram in [-40, 40] range
  - Returns averaged histogram (32 bins)
- `analyze_video()`: Classifies video as cover or stego
  - Extracts features from frames
  - Uses SVM to classify
  - Returns result with confidence

#### SVM Details
- **Kernel**: RBF
- **C**: 1.0
- **Feature Extraction**: Residual histograms (32 dimensions)

### 7. **utils_av.py** - Utility Functions

#### Functions
- `extract_audio_from_video()`: Extracts audio track from video using ffmpeg
- `ensure_dir()`: Creates directory if not exists

---

## SVM Classifiers

### Audio SVM
- **Purpose**: Detect MFCC anomalies from LSB embedding
- **Features**: MFCC (Mel-Frequency Cepstral Coefficients)
- **Training Data**: Cover audio vs. LSB-embedded audio
- **Model Path**: `models/audio_svm.joblib`
- **Scaler Path**: `models/audio_scaler.joblib`

**How It Works**:
1. Extract MFCC features from audio
2. Scale features with pretrained scaler
3. Pass to SVM classifier
4. Get probability of steganography presence

### Video SVM
- **Purpose**: Detect pixel LSB modifications
- **Features**: Residual histograms
  - Compute Gaussian blur of frame
  - Calculate residuals: pixel - blur
  - Create histogram of residuals
- **Training Data**: Cover video frames vs. LSB-embedded video frames
- **Model Path**: `models/video_svm.joblib`
- **Scaler Path**: `models/video_scaler.joblib`

**How It Works**:
1. Sample video frames
2. Extract residual histogram features
3. Scale features
4. Pass to SVM classifier
5. Get probability of steganography

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- ffmpeg installed and in PATH
- 2GB+ disk space for models and data

### Step 1: Clone/Download Project
```bash
cd "C:\Users\user\Desktop\EECE 632- Cryptography and Network Security\StegDetector\StegDetector"
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# or: source venv/bin/activate  # On macOS/Linux
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run Application
```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`

---

## Usage Guide

### Basic Workflow

#### 1. Sign Up / Login
1. Go to "Sign Up" tab if new user
2. Enter username and password (must meet requirements)
3. Account automatically created and logged in
4. Or use "Login" tab for existing users

#### 2. Embed a Message

**Audio File**:
1. Go to "Embed" tab
2. Upload audio file (WAV, MP3, FLAC, OGG, M4A)
3. Enter secret message
4. Click "Embed message"
5. Download stego audio file

**Video File - Single Message**:
1. Upload video file
2. Select embedding mode:
   - "Video frames only": Message in pixels
   - "Audio track only": Message in audio
3. Enter message
4. Click "Embed message"
5. Download .mkv file

**Video File - Dual Messages**:
1. Upload video file
2. Select "Both frames + audio"
3. Uncheck "Use the same message..."
4. Enter message for video frames
5. Enter message for audio track
6. Click "Embed message"
7. Download .mkv file with both stegos

#### 3. Extract a Message

**Audio File**:
1. Go to "Extract" tab
2. Upload stego audio file
3. Click "Extract message"
4. Hidden message displayed in code block

**Video File**:
1. Upload stego video
2. Select extraction mode:
   - "Auto": Extracts from frames AND audio
   - "Video frames only": Extracts message from pixels
   - "Audio track only": Extracts message from audio
3. Click "Extract message"
4. Message displayed (shows recovered text or error message)

#### 4. Analyze File

1. Go to "Analyze" tab
2. Upload file (audio or video)
3. Click "Run analysis"
4. JSON result shows:
   - Classification (cover or stego)
   - Confidence scores
   - Feature values used

---

## Development Notes

### Important Considerations

#### 1. Color Space in Video
- Input video may be YUV420p (most common)
- Imageio converts to RGB on read
- Must work in consistent RGB space
- FFV1 re-encodes but preserves exact pixel values

#### 2. File Size Trade-off
- FFV1 is lossless → larger files than lossy codecs
- But necessary to preserve LSBs for steganography
- 9MB input → ~150MB output (typical ratio)
- Alternative: Use H.264 but loses LSBs on compression

#### 3. Timestamp Synchronization
- ffmpeg muxing needs proper timestamp handling
- Use `-shortest` flag to avoid sync issues
- FLAC audio codec more compatible than PCM in MKV

#### 4. LSB Embedding Safety
- Only modifies least significant bit of each byte
- Preserves 7/8 of original data in each byte
- Changes imperceptible to human perception
- But extractable and analyzable by SVM

#### 5. Message Capacity
- Audio: ~1 bit per sample × sample rate × duration
  - 44100 Hz stereo 10 seconds = ~441,000 bytes capacity
- Video: ~3 bits per pixel × frame size × frame rate × duration
  - 1280×720 30 fps 10 seconds = ~82,944,000 bytes capacity

### Testing Checklist
- [ ] Audio embedding/extraction works
- [ ] Video frames embedding/extraction works
- [ ] Video audio track embedding/extraction works
- [ ] Dual message embedding works
- [ ] SVM analysis correctly detects stego
- [ ] File size reasonable for lossless format
- [ ] Audio/video plays correctly after stego
- [ ] Temp files cleaned up properly
- [ ] User authentication working
- [ ] Error messages informative

### Future Improvements
1. **Reduce File Size**: Implement lossy-but-LSB-preserving codec
2. **Improve SVM Accuracy**: Use larger/more diverse datasets
3. **Deep Learning**: Replace SVM with CNN classifier
4. **Batch Processing**: Embed/extract from multiple files
5. **Encryption**: Add encryption to embedded messages
6. **Stealth Detection**: Implement more advanced steganalysis methods
7. **Progress Bars**: Add progress indication for long operations
8. **Database**: Store analysis history

---

## Troubleshooting

### ffmpeg Not Found
**Solution**: Install ffmpeg from https://ffmpeg.org/download.html
- Add to Windows PATH: `C:\ffmpeg\bin`
- Verify: `ffmpeg -version` in terminal

### soundfile Module Error
**Solution**: Reinstall with binary dependencies
```bash
pip install --upgrade soundfile
```

### Video Won't Play After Stego
**Solution**: Use FFV1 + FLAC (current implementation)
- Ensures LSBs preserved
- Compatible with most players

### Extraction Returns Empty Message
**Solution**: 
- Check if stego was properly created
- Ensure using matching extraction method (frames vs audio)
- Video must have audio track for audio extraction

### SVM Analysis Not Working
**Solution**:
- Ensure models exist in `models/` directory
- Run training scripts: `python training/train_audio_svm.py`
- Check model paths in detector files

---

## References & Resources

- **Steganography**: https://en.wikipedia.org/wiki/Steganography
- **LSB Steganography**: Principle of modifying least significant bits
- **MFCC Features**: https://librosa.org/doc/main/generated/librosa.feature.mfcc.html
- **SVM Classification**: https://scikit-learn.org/stable/modules/svm.html
- **FFmpeg**: https://ffmpeg.org/ffmpeg.html
- **Streamlit Documentation**: https://docs.streamlit.io/

---

## Contact & Support

For questions about the project or modifications made:
- Review the `PROJECT_DOCUMENTATION.md` file (this file)
- Check `SVM_CLASSIFIER_DOCUMENTATION.md` for ML details
- Review code comments in source files
- Run training scripts with debug output enabled

---

**Last Updated**: November 30, 2025
**Course**: EECE 632 - Cryptography and Network Security
**Project Status**: Active Development
