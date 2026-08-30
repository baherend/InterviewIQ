# 🎙️ Audio Emotion Recognition — Production Package

Self-contained Python package for **Vocal Emotion Recognition** using Wav2Vec2-Large-XLSR-53 + BiLSTM.

**Model Performance:** 89.15% Accuracy | 89.19% Macro F1 | 86.36% Neutral Precision

---

## 📋 Quick Start

```python
from audio_module import predict_emotion

result = predict_emotion("path/to/audio.wav")
print(result["dominant_emotion"])    # "High Emotion"
print(result["confidence_score"])    # 0.85
print(result["emotion_scores"])      # {"Low Emotion": 0.08, ...}
```

---

## 📦 Package Contents

| File | Description |
|------|-------------|
| `audio_module.py` | Core inference module with `AudioEmotionPredictor` class |
| `audio_model.pt` | PyTorch model weights (631,884,518 bytes; intentionally Git-ignored) |
| `config.json` | Model and audio configuration |
| `labels.json` | Emotion index-to-label mapping |
| `requirements.txt` | Python dependencies |
| `test_sample.wav` | Sample audio file for testing |
| `expected_output.json` | Reference output format |

---

## 🔧 System Requirements

### Python Version
- **Required:** Python 3.10 or 3.11
- **Recommended:** Python 3.11

### Hardware
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| GPU VRAM | — | 2-3 GB (CUDA) |
| CPU | Any modern x86_64 | Multi-core |
| Disk | 2 GB free | 5 GB free |

**GPU Support:** Optional. Falls back to CPU automatically if CUDA is not available.

### FFmpeg Requirement
FFmpeg is required for non-WAV audio formats (`.mp3`, `.ogg`, `.flac`, `.m4a`).

**Install FFmpeg:**
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg
```

WAV files do NOT require FFmpeg.

---

## 📥 Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Install FFmpeg for non-WAV formats
# See FFmpeg Requirement section above
```

---

## 🎵 Audio Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Sample Rate** | 16,000 Hz | Auto-resampled if different |
| **Channels** | Mono (1) | Auto-converted if stereo |
| **Bit Depth** | 32-bit float | Internal processing |
| **Supported Formats** | `.wav`, `.mp3`, `.ogg`, `.flac` | FFmpeg needed for non-WAV |
| **Optimal Duration** | 3-10 seconds | Shorter = less reliable |
| **Max Duration** | 10 seconds | Longer clips are truncated |
| **Min Duration** | ~0.5 seconds | After silence removal |

### Preprocessing Pipeline
1. **Load:** Audio file → mono float32 waveform
2. **Resample:** Convert to 16,000 Hz (if different)
3. **Normalize:** Peak normalization to [-1.0, 1.0]
4. **VAD:** Silence removal (RMS energy threshold)
5. **Truncate:** Cap at max_duration_sec (10s)
6. **Extract:** Wav2Vec2 features → BiLSTM → softmax

---

## 🏷️ Label Ordering

The model outputs 3 classes in this exact order:

| Index | Label | Description |
|-------|-------|-------------|
| 0 | Low Emotion | Calm, subdued, low activation |
| 1 | Neutral Emotion | Professional, objective |
| 2 | High Emotion | Excited, energetic, high activation |

**Important:** When interpreting raw logits or probabilities, index 0 = Low, index 1 = Neutral, index 2 = High.

---

## 📤 Output Format

```json
{
  "dominant_emotion": "High Emotion",
  "emotion_scores": {
    "Low Emotion": 0.08,
    "Neutral Emotion": 0.22,
    "High Emotion": 0.70
  },
  "confidence_score": 0.70
}
```

| Field | Type | Description |
|-------|------|-------------|
| `dominant_emotion` | str | Highest probability class |
| `emotion_scores` | dict | Probability for each class (sums to 1.0) |
| `confidence_score` | float | Probability of dominant class |

---

## 🧪 Testing

### Run Built-in Test
```bash
python audio_module.py
```

### Test with Custom Audio
```bash
python audio_module.py path/to/your/audio.wav
```

### Verify Installation
```python
from audio_module import predict_emotion

# Test with included sample
result = predict_emotion("test_sample.wav")
assert "dominant_emotion" in result
assert "emotion_scores" in result
assert "confidence_score" in result
print("✓ Package working correctly")
```

---

## 🔌 Backend Integration

### FastAPI Example
```python
from fastapi import FastAPI, UploadFile
from audio_module import predict_emotion
import tempfile

app = FastAPI()

@app.post("/predict")
async def predict(file: UploadFile):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await file.read())
        result = predict_emotion(tmp.name)
    return result
```

### Flask Example
```python
from flask import Flask, request, jsonify
from audio_module import predict_emotion
import tempfile

app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():
    file = request.files["file"]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        file.save(tmp.name)
        result = predict_emotion(tmp.name)
    return jsonify(result)
```

---

## 🏗️ Architecture

```
Audio (16kHz, mono)
    ↓
Wav2Vec2-Large-XLSR-53 (frozen encoder)
    ↓ [Batch, T=150, D=1024]
BiLSTM (hidden=50, bidirectional)
    ↓
Mean Pooling → [Batch, 100]
    ↓
Dropout (0.2)
    ↓
Linear (100 → 3)
    ↓
Softmax → [Low, Neutral, High]
```

**Total Parameters:** ~315M (311M trainable)

---

## 📊 Model Details

- **Paper:** Mohamed & Aly (2021) — Arabic Speech Emotion Recognition Employing Wav2vec2.0
- **Dataset:** BAVED (1,935 samples, 60 speakers, 3 classes)
- **Training:** Cosine scheduler with 10% warmup, Focal Loss, class weights
- **Best Checkpoint:** Model 09 (Cosine_Warmup10pct)

---

## ⚠️ Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `FileNotFoundError` | Audio file not found | Check file path |
| `ValueError: Invalid audio` | Corrupt or unsupported format | Convert to WAV |
| `FileNotFoundError: Model` | `audio_model.pt` missing | Ensure model file is in package |
| `RuntimeError: CUDA` | GPU memory issue | Will auto-fallback to CPU |

---

## 📄 License

MIT License — See project root for details.
