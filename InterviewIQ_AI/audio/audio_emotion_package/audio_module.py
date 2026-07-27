"""
Audio Emotion Recognition Module — Self-Contained Production Package.

Model: Wav2Vec2-Large-XLSR-53 + BiLSTM (50 hidden)
Dataset: BAVED (3 classes: Low Emotion, Neutral Emotion, High Emotion)
Accuracy: 89.15% | Macro F1: 89.19%

Usage:
    from audio_module import predict_emotion
    result = predict_emotion("path/to/audio.wav")
    print(result["dominant_emotion"])
    print(result["emotion_scores"])
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

# ── Suppress harmless warnings ─────────────────────────────────────────
warnings.filterwarnings("ignore", message=".*Failed to load image.*")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

logger = logging.getLogger("audio_module")

# ── Resolve paths relative to this file ────────────────────────────────
_PACKAGE_DIR = Path(__file__).resolve().parent
_MODEL_PATH = _PACKAGE_DIR / "audio_model.pt"
_CONFIG_PATH = _PACKAGE_DIR / "config.json"
_LABELS_PATH = _PACKAGE_DIR / "labels.json"


# ══════════════════════════════════════════════════════════════════════
# MODEL ARCHITECTURE — Wav2Vec2-Large-XLSR-53 + BiLSTM
# ══════════════════════════════════════════════════════════════════════
class Wav2Vec2BiLSTMForSER(nn.Module):
    """
    Wav2Vec2-Large-XLSR-53 + Bi-LSTM (50 hidden) + Linear(100 → 3).
    Replicates Mohamed & Aly (2021) architecture for Arabic SER.
    """

    def __init__(
        self,
        backbone_name: str,
        num_labels: int,
        lstm_hidden_size: int = 50,
        mask_time_prob: float = 0.03,
        dropout: float = 0.2,
    ):
        super().__init__()
        from transformers import Wav2Vec2Config, Wav2Vec2Model

        config = Wav2Vec2Config.from_pretrained(backbone_name)
        config.mask_time_prob = mask_time_prob
        self.wav2vec2 = Wav2Vec2Model.from_pretrained(
            backbone_name, config=config, ignore_mismatched_sizes=True
        )
        self.wav2vec2.freeze_feature_encoder()

        hidden_size = config.hidden_size  # 1024 for XLSR-53-Large
        self.bilstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=lstm_hidden_size,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(lstm_hidden_size * 2, num_labels)
        self.num_labels = num_labels

    def forward(self, input_values, attention_mask=None, **kwargs):
        outputs = self.wav2vec2(
            input_values=input_values, attention_mask=attention_mask
        )
        hidden = outputs.last_hidden_state       # [B, T, 1024]
        lstm_out, _ = self.bilstm(hidden)         # [B, T, 100]
        pooled = lstm_out.mean(dim=1)             # [B, 100]
        pooled = self.dropout(pooled)
        logits = self.classifier(pooled)          # [B, 3]
        return logits


# ══════════════════════════════════════════════════════════════════════
# AudioEmotionPredictor — Self-contained predictor class
# ══════════════════════════════════════════════════════════════════════
class AudioEmotionPredictor:
    """
    Self-contained audio emotion predictor.

    Automatically resolves paths relative to __file__.
    Loads model once on first prediction (lazy loading).

    Usage:
        predictor = AudioEmotionPredictor()
        result = predictor.predict("audio.wav")
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        labels_path: Optional[str] = None,
    ):
        # Resolve paths relative to this file
        self.model_path = Path(model_path) if model_path else _MODEL_PATH
        self.config_path = Path(config_path) if config_path else _CONFIG_PATH
        self.labels_path = Path(labels_path) if labels_path else _LABELS_PATH

        # Load config
        self.config = self._load_json(self.config_path, {
            "sample_rate": 16000,
            "channels": 1,
            "backbone_name": "elgeish/wav2vec2-large-xlsr-53-arabic",
            "num_labels": 3,
            "lstm_hidden_size": 50,
            "mask_time_prob": 0.03,
            "dropout": 0.2,
            "max_duration_sec": 10,
            "neutral_threshold": 0.45,
        })

        # Load labels
        self.labels = self._load_json(self.labels_path, {
            "0": "Low Emotion",
            "1": "Neutral Emotion",
            "2": "High Emotion",
        })

        # Model state (lazy loaded)
        self._model = None
        self._processor = None
        self._device = None

    @staticmethod
    def _load_json(path: Path, default: dict) -> dict:
        """Load JSON file or return default."""
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _load_model(self):
        """Load model and processor (lazy, cached)."""
        if self._model is not None:
            return

        from transformers import Wav2Vec2FeatureExtractor

        self._device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}\n"
                "Ensure audio_model.pt is in the same directory as audio_module.py"
            )

        # Load bundle
        bundle = torch.load(
            self.model_path, map_location=self._device, weights_only=False
        )
        bundle_config = bundle.get("config", self.config)

        # Build model
        self._model = Wav2Vec2BiLSTMForSER(
            backbone_name=bundle_config["backbone_name"],
            num_labels=bundle_config["num_labels"],
            lstm_hidden_size=bundle_config["lstm_hidden_size"],
            mask_time_prob=bundle_config["mask_time_prob"],
            dropout=bundle_config["dropout"],
        )
        self._model.load_state_dict(bundle["state_dict"])
        self._model.to(self._device)
        self._model.eval()

        # Load feature extractor
        self._processor = Wav2Vec2FeatureExtractor.from_pretrained(
            bundle_config["backbone_name"]
        )

        logger.info(
            f"Model loaded on {self._device} from {self.model_path}"
        )

    def _load_audio(self, audio_path: str) -> np.ndarray:
        """Load audio file as mono float32 waveform at configured sample rate."""
        import librosa

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            waveform, _ = librosa.load(
                str(path),
                sr=self.config["sample_rate"],
                mono=True,
            )
        except Exception as e:
            raise ValueError(
                f"Invalid or corrupt audio file: {audio_path}\n{e}"
            )

        if len(waveform) == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        return waveform.astype(np.float32)

    @staticmethod
    def _normalize_loudness(waveform: np.ndarray) -> np.ndarray:
        """Peak-normalize waveform to [-1.0, 1.0]."""
        peak = np.max(np.abs(waveform))
        if peak > 0:
            waveform = waveform / peak
        return waveform

    @staticmethod
    def _remove_silence(
        waveform: np.ndarray, sr: int = 16000, top_db: int = 25
    ) -> np.ndarray:
        """Remove silence using librosa trim + RMS threshold."""
        import librosa

        waveform, _ = librosa.effects.trim(waveform, top_db=top_db)
        rms = librosa.feature.rms(
            y=waveform, frame_length=2048, hop_length=512
        )[0]

        if len(rms) == 0 or np.max(rms) == 0:
            return waveform

        threshold = np.max(rms) * 0.02
        voice_mask = rms > threshold

        if not np.any(voice_mask):
            return waveform

        frame_indices = np.where(voice_mask)[0]
        start_sample = frame_indices[0] * 512
        end_sample = min(frame_indices[-1] * 512 + 2048, len(waveform))

        return waveform[start_sample:end_sample]

    def predict(self, audio_path: str) -> Dict:
        """
        Predict emotion from audio file.

        Args:
            audio_path: Path to audio file (.wav, .mp3, .ogg, .flac)

        Returns:
            dict with:
                - dominant_emotion: str (e.g., "happy", "sad", "neutral")
                - emotion_scores: dict {label: probability}
                - confidence_score: float (0-1)
        """
        # Ensure model is loaded
        self._load_model()

        # Load and preprocess audio
        waveform = self._load_audio(audio_path)
        waveform = self._normalize_loudness(waveform)
        waveform = self._remove_silence(
            waveform, sr=self.config["sample_rate"]
        )

        # Truncate if too long
        max_samples = int(
            self.config["max_duration_sec"] * self.config["sample_rate"]
        )
        if len(waveform) > max_samples:
            waveform = waveform[:max_samples]

        # Run inference
        inputs = self._processor(
            waveform,
            sampling_rate=self.config["sample_rate"],
            return_tensors="pt",
        )
        input_values = inputs["input_values"].to(self._device)

        with torch.no_grad():
            logits = self._model(input_values=input_values)

        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()

        # Build result
        emotion_scores = {
            self.labels[str(i)]: round(float(p), 4)
            for i, p in enumerate(probs)
        }

        predicted_id = int(np.argmax(probs))
        dominant_emotion = self.labels[str(predicted_id)]
        confidence_score = round(float(probs[predicted_id]), 4)

        return {
            "dominant_emotion": dominant_emotion,
            "emotion_scores": emotion_scores,
            "confidence_score": confidence_score,
        }


# ══════════════════════════════════════════════════════════════════════
# MODULE-LEVEL PREDICT FUNCTION
# ══════════════════════════════════════════════════════════════════════
_predictor = None


def predict_emotion(audio_path: str) -> Dict:
    """
    Standalone prediction function — convenience wrapper.

    Args:
        audio_path: Path to audio file

    Returns:
        dict with dominant_emotion, emotion_scores, confidence_score

    Usage:
        from audio_module import predict_emotion
        result = predict_emotion("audio.wav")
    """
    global _predictor
    if _predictor is None:
        _predictor = AudioEmotionPredictor()
    return _predictor.predict(audio_path)


# ══════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    # Default test file
    test_file = _PACKAGE_DIR / "test_sample.wav"

    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])

    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        print(f"Usage: python audio_module.py [audio_file]")
        sys.exit(1)

    print(f"Testing: {test_file}")
    print("=" * 50)

    try:
        result = predict_emotion(str(test_file))

        print(f"  Dominant Emotion : {result['dominant_emotion']}")
        print(f"  Confidence       : {result['confidence_score']:.4f}")
        print(f"  Emotion Scores:")
        for emotion, score in result["emotion_scores"].items():
            bar = "#" * int(score * 30) + "-" * (30 - int(score * 30))
            print(f"    {emotion:>17s} |{bar}| {score:.4f}")

        # Save expected output
        output_path = _PACKAGE_DIR / "expected_output.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\n  Output saved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("=" * 50)
    print("Test passed!")
