"""
Local runtime port of VSC_RAVDESS_LoRA_R16_Visual_Confidence.ipynb.

Reuses the notebook's model architecture (Swin-T backbone + LoRA r16 +
TCN + temporal attention pooling), preprocessing (MTCNN largest-face
crop + JPEG round-trip + ImageNet normalization), checkpoint-loading
logic (key normalization from `backbone.*` to `backbone.model.*`), and
the temporal-window / visual-behavioral-confidence-score pipeline
almost line-for-line. Kaggle-specific paths, plotting cells, and the
optional batch/CSV helpers were dropped; everything else is preserved.

Entry point: analyze_visual_confidence(video_path: str) -> dict
"""

from __future__ import annotations

import json
import math
import os
import time
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

warnings.filterwarnings("ignore")

try:
    import cv2
except ImportError as _cv2_import_error:  # pragma: no cover
    cv2 = None
    _CV2_IMPORT_ERROR = _cv2_import_error
else:
    _CV2_IMPORT_ERROR = None

try:
    import torchvision.models as tv_models
    from torchvision import transforms
except ImportError as _tv_import_error:  # pragma: no cover
    tv_models = None
    transforms = None
    _TV_IMPORT_ERROR = _tv_import_error
else:
    _TV_IMPORT_ERROR = None

try:
    from PIL import Image
except ImportError as _pil_import_error:  # pragma: no cover
    Image = None
    _PIL_IMPORT_ERROR = _pil_import_error
else:
    _PIL_IMPORT_ERROR = None

try:
    from facenet_pytorch import MTCNN
except ImportError as _mtcnn_import_error:
    MTCNN = None
    _MTCNN_IMPORT_ERROR = _mtcnn_import_error
else:
    _MTCNN_IMPORT_ERROR = None


# =============================================================================
# Errors
# =============================================================================

class VisionModuleError(Exception):
    """Base class for vision_module runtime errors."""


class MissingDependencyError(VisionModuleError):
    pass


class VideoNotFoundError(VisionModuleError):
    pass


class VideoUnreadableError(VisionModuleError):
    pass


class InsufficientFramesError(VisionModuleError):
    pass


class CheckpointNotFoundError(VisionModuleError):
    pass


class CheckpointIncompatibleError(VisionModuleError):
    pass


# =============================================================================
# Paths (pathlib, relative to this module — no Kaggle paths)
# =============================================================================

MODULE_DIR = Path(__file__).resolve().parent
DEPLOYMENT_DIR = MODULE_DIR / "vsc_ravdess_test73_deployment (1)"
DEFAULT_CHECKPOINT_PATH = DEPLOYMENT_DIR / "vsc_ravdess_lora_r16_test73_24.pt"
CONFIG_JSON_PATH = DEPLOYMENT_DIR / "config.json"
LABELS_JSON_PATH = DEPLOYMENT_DIR / "labels.json"


# =============================================================================
# Labels / classes
# =============================================================================

# Exact class order the checkpoint was trained with (notebook cell 5).
# `config.json` in the deployment folder is empty (0 bytes) and the notebook
# never reads it for classes/config, so this hardcoded order is the source
# of truth, cross-checked against labels.json below.
MODEL_CLASSES: List[str] = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

RAVDESS_CODE_TO_EMOTION: Dict[str, str] = {
    "01": "neutral",
    "02": "calm",
    "03": "happy",
    "04": "sad",
    "05": "angry",
    "06": "fearful",
    "07": "disgust",
    "08": "surprised",
}


def _labels_json_matches_model_classes() -> Optional[bool]:
    if not LABELS_JSON_PATH.is_file():
        return None
    try:
        payload = json.loads(LABELS_JSON_PATH.read_text(encoding="utf-8"))
        return list(payload.get("classes", [])) == MODEL_CLASSES
    except (json.JSONDecodeError, OSError):
        return None


# =============================================================================
# Configs (notebook cells 5 and 29, verbatim)
# =============================================================================

@dataclass
class ModelConfig:
    num_frames: int = 16
    image_size: int = 224
    num_classes: int = 8

    swin_feature_dim: int = 768

    tcn_channels: Tuple[int, int, int] = (256, 256, 256)
    tcn_kernel_size: int = 3
    tcn_dropout: float = 0.3

    attention_hidden_dim: int = 128

    lora_rank: int = 16
    lora_alpha: float = 32.0

    face_margin: float = 0.10
    min_face_probability: float = 0.50


CFG = ModelConfig()


@dataclass
class VisualConfidenceConfig:
    # Video windowing
    window_seconds: float = 4.0
    stride_seconds: float = 4.0
    minimum_last_window_seconds: float = 1.5

    # Negative Affect = raw sum of (Sad + Disgust + Fearful + Angry)
    # probabilities. Weights are severity multipliers, not proportions
    # that must sum to 1.0 (see notebook cell 29 for rationale).
    negative_affect_threshold: float = 0.25
    sad_weight: float = 1.0
    disgust_weight: float = 1.0
    fearful_weight: float = 1.0
    angry_weight: float = 1.0

    # Calm recovery
    recovery_horizon_windows: int = 2
    recovery_minimum_signal: float = 0.40
    recovery_minimum_gain: float = 0.10

    # Measurement reliability
    minimum_windows_for_decision: int = 3
    minimum_face_detection_ratio: float = 0.60

    # Comfort Signal = raw sum of (Calm + Neutral + Happy)
    calm_weight: float = 1.0
    neutral_weight: float = 1.0
    happy_weight: float = 1.0

    # Base score weights (must sum to 1.0 — each component is already 0-1)
    comfort_weight: float = 0.35
    stability_weight: float = 0.25
    recovery_weight: float = 0.20
    negative_affect_weight: float = 0.20

    # Confidence interval
    confidence_interval_max_margin: float = 15.0

    def validate(self) -> None:
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")

        if self.stride_seconds <= 0:
            raise ValueError("stride_seconds must be positive.")

        comfort_weights = [self.calm_weight, self.neutral_weight, self.happy_weight]
        if any(w < 0 for w in comfort_weights):
            raise ValueError(
                "calm_weight, neutral_weight, happy_weight must be non-negative."
            )

        negative_weights = [
            self.sad_weight,
            self.disgust_weight,
            self.fearful_weight,
            self.angry_weight,
        ]
        if any(w < 0 for w in negative_weights):
            raise ValueError(
                "sad_weight, disgust_weight, fearful_weight, angry_weight "
                "must be non-negative."
            )

        base_weights = (
            self.comfort_weight
            + self.stability_weight
            + self.recovery_weight
            + self.negative_affect_weight
        )
        if abs(base_weights - 1.0) > 1e-6:
            raise ValueError(
                "comfort_weight + stability_weight + recovery_weight "
                "+ negative_affect_weight must sum to 1.0."
            )

        if self.confidence_interval_max_margin < 0:
            raise ValueError("confidence_interval_max_margin must be non-negative.")


VISUAL_CFG = VisualConfidenceConfig()
VISUAL_CFG.validate()


# =============================================================================
# LoRA + model architecture (notebook cells 7, 8, 9 — verbatim)
# =============================================================================

class LoRALinear(nn.Module):
    """LoRA wrapper compatible with qkv inside torchvision Swin Transformer."""

    def __init__(
        self,
        original_linear: nn.Linear,
        rank: int = 16,
        alpha: float = 32.0,
    ) -> None:
        super().__init__()

        if not isinstance(original_linear, nn.Linear):
            raise TypeError("original_linear must be nn.Linear")

        self.original_linear = original_linear

        for parameter in self.original_linear.parameters():
            parameter.requires_grad = False

        in_features = original_linear.in_features
        out_features = original_linear.out_features

        self.lora_A = nn.Parameter(torch.zeros(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))

        self.scaling = float(alpha) / float(rank)

        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    @property
    def weight(self) -> torch.Tensor:
        target_device = self.original_linear.weight.device

        lora_A = self.lora_A.to(target_device)
        lora_B = self.lora_B.to(target_device)

        delta = (lora_B @ lora_A) * self.scaling

        return self.original_linear.weight + delta

    @property
    def bias(self):
        return self.original_linear.bias

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return nn.functional.linear(x, self.weight, self.bias)


def inject_lora_to_swin(model: nn.Module, rank: int = 16, alpha: float = 32.0) -> int:
    """Inject LoRA into qkv of every ShiftedWindowAttention block."""

    injected_count = 0

    for _, module in model.named_modules():
        if module.__class__.__name__ != "ShiftedWindowAttention":
            continue

        if hasattr(module, "qkv") and isinstance(module.qkv, nn.Linear):
            module.qkv = LoRALinear(module.qkv, rank=rank, alpha=alpha)
            injected_count += 1

    return injected_count


class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int) -> None:
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.chomp_size == 0:
            return x

        return x[:, :, :-self.chomp_size].contiguous()


class TCNBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
        super().__init__()

        padding = (kernel_size - 1) * dilation

        self.conv1 = nn.Conv1d(
            in_channels, out_channels, kernel_size, padding=padding, dilation=dilation
        )
        self.chomp1 = Chomp1d(padding)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(
            out_channels, out_channels, kernel_size, padding=padding, dilation=dilation
        )
        self.chomp2 = Chomp1d(padding)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = (
            nn.Conv1d(in_channels, out_channels, 1)
            if in_channels != out_channels
            else None
        )

        self.relu_out = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output = self.drop1(self.relu1(self.bn1(self.chomp1(self.conv1(x)))))
        output = self.drop2(self.relu2(self.bn2(self.chomp2(self.conv2(output)))))

        residual = x if self.downsample is None else self.downsample(x)

        return self.relu_out(output + residual)


class TemporalConvNet(nn.Module):
    def __init__(
        self,
        input_dim: int,
        channels: Sequence[int],
        kernel_size: int = 3,
        dropout: float = 0.3,
        dilations: Optional[Sequence[int]] = None,
    ) -> None:
        super().__init__()

        if dilations is None:
            dilations = [2 ** index for index in range(len(channels))]

        if len(dilations) != len(channels):
            raise ValueError("Number of dilations must equal number of TCN channels.")

        blocks = []
        previous_channels = input_dim

        for output_channels, dilation in zip(channels, dilations):
            blocks.append(
                TCNBlock(
                    in_channels=previous_channels,
                    out_channels=output_channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
            previous_channels = output_channels

        self.network = nn.Sequential(*blocks)
        self.output_dim = int(channels[-1])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # [B, T, F] -> [B, F, T]
        x = x.transpose(1, 2)
        x = self.network(x)
        # [B, F, T] -> [B, T, F]
        return x.transpose(1, 2)


class TemporalAttentionPooling(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()

        self.attention = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        scores = self.attention(x)
        weights = torch.softmax(scores, dim=1)

        return (weights * x).sum(dim=1)


class SwinFeatureExtractor(nn.Module):
    """Wrapper that preserves the checkpoint key layout: backbone.model.*"""

    def __init__(self) -> None:
        super().__init__()

        if tv_models is None:
            raise MissingDependencyError(
                "torchvision is required but not installed: "
                f"{_TV_IMPORT_ERROR}"
            )

        # weights=None avoids needing internet access; all weights come
        # from the checkpoint.
        self.model = tv_models.swin_t(weights=None)

        self.feature_dim = self.model.head.in_features
        self.model.head = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, time_steps, channels, height, width = x.shape

        x = x.reshape(batch_size * time_steps, channels, height, width)

        features = self.model(x)

        return features.reshape(batch_size, time_steps, -1)


class VSCClassifier(nn.Module):
    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__()

        self.backbone = SwinFeatureExtractor()

        self.tcn = TemporalConvNet(
            input_dim=cfg.swin_feature_dim,
            channels=cfg.tcn_channels,
            kernel_size=cfg.tcn_kernel_size,
            dropout=cfg.tcn_dropout,
            dilations=(1, 2, 4),
        )

        self.aggregator = TemporalAttentionPooling(
            input_dim=cfg.tcn_channels[-1],
            hidden_dim=cfg.attention_hidden_dim,
        )

        self.fc = nn.Linear(cfg.tcn_channels[-1], cfg.num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        spatial_features = self.backbone(x)
        temporal_features = self.tcn(spatial_features)
        pooled_features = self.aggregator(temporal_features)

        return self.fc(pooled_features)


# =============================================================================
# Checkpoint loading (notebook cell 11, adapted for local paths + errors)
# =============================================================================

def _safe_torch_load(checkpoint_path: str, map_location: torch.device):
    try:
        return torch.load(checkpoint_path, map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(checkpoint_path, map_location=map_location)


def normalize_checkpoint_keys(
    state_dict: Dict[str, torch.Tensor],
) -> Tuple[Dict[str, torch.Tensor], str]:
    """Normalize checkpoint keys to match the current VSCClassifier layout."""

    normalized = {}
    changes = []

    for original_key, tensor in state_dict.items():
        key = original_key

        if key.startswith("module."):
            key = key[len("module."):]
            changes.append("removed module")

        if key.startswith("backbone.") and not key.startswith("backbone.model."):
            key = "backbone.model." + key[len("backbone."):]
            changes.append("added backbone.model")

        normalized[key] = tensor

    if "added backbone.model" in changes:
        layout = "added backbone.model"
    elif "removed module" in changes:
        layout = "removed module"
    else:
        layout = "original"

    return normalized, layout


def load_vsc_model(
    checkpoint_path: Path,
    device: torch.device,
) -> Tuple[nn.Module, List[str], dict, torch.device]:
    checkpoint_path_str = str(checkpoint_path)

    if not os.path.isfile(checkpoint_path_str):
        raise CheckpointNotFoundError(
            f"Checkpoint not found: {checkpoint_path_str}"
        )

    try:
        checkpoint = _safe_torch_load(checkpoint_path_str, map_location=device)
    except Exception as error:
        raise CheckpointIncompatibleError(
            f"Failed to load checkpoint file: {error}"
        ) from error

    state_dict = (
        checkpoint["model_state"]
        if isinstance(checkpoint, dict) and "model_state" in checkpoint
        else checkpoint
    )

    if not isinstance(state_dict, dict):
        raise CheckpointIncompatibleError("Unsupported checkpoint format.")

    model = VSCClassifier(CFG)

    injected_count = inject_lora_to_swin(
        model.backbone.model,
        rank=CFG.lora_rank,
        alpha=CFG.lora_alpha,
    )

    normalized_state, key_layout = normalize_checkpoint_keys(state_dict)

    try:
        load_result = model.load_state_dict(normalized_state, strict=True)
    except RuntimeError as error:
        raise CheckpointIncompatibleError(
            f"Checkpoint is incompatible with the model architecture: {error}"
        ) from error

    model = model.to(device)
    model.float()
    model.eval()

    classes = (
        checkpoint.get("classes", MODEL_CLASSES)
        if isinstance(checkpoint, dict)
        else MODEL_CLASSES
    )

    if list(classes) != MODEL_CLASSES:
        raise CheckpointIncompatibleError(
            f"Unexpected class order in checkpoint: {classes}"
        )

    metadata = {}
    if isinstance(checkpoint, dict):
        metadata = {
            "epoch": checkpoint.get("epoch"),
            "validation_accuracy": checkpoint.get(
                "validation_accuracy", checkpoint.get("val_acc", checkpoint.get("val_accuracy"))
            ),
            "test_accuracy": checkpoint.get("test_accuracy"),
            "lora_layers_injected": injected_count,
            "checkpoint_key_layout": key_layout,
            "missing_keys_count": len(load_result.missing_keys),
            "unexpected_keys_count": len(load_result.unexpected_keys),
        }

    return model, list(classes), metadata, device


# Module-level cache: (checkpoint_path, device.type) -> loaded model bundle.
_MODEL_CACHE: Dict[Tuple[str, str], Tuple[nn.Module, List[str], dict, torch.device]] = {}


def _select_device(warnings_out: List[str]) -> torch.device:
    if not torch.cuda.is_available():
        return torch.device("cpu")

    try:
        device = torch.device("cuda")
        # Small probe to catch CUDA driver/runtime failures early.
        probe = torch.zeros(1, device=device)
        del probe
        return device
    except Exception as error:  # pragma: no cover - depends on local GPU state
        warnings_out.append(f"CUDA is available but failed to initialize ({error}); falling back to CPU.")
        return torch.device("cpu")


def get_model(
    checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
    device: Optional[torch.device] = None,
    warnings_out: Optional[List[str]] = None,
) -> Tuple[nn.Module, List[str], dict, torch.device]:
    warnings_out = warnings_out if warnings_out is not None else []

    if device is None:
        device = _select_device(warnings_out)

    cache_key = (str(checkpoint_path), device.type)

    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    try:
        bundle = load_vsc_model(checkpoint_path, device)
    except CheckpointIncompatibleError:
        raise
    except CheckpointNotFoundError:
        raise
    except Exception as error:
        if device.type == "cuda":
            warnings_out.append(
                f"Model failed to load on CUDA ({error}); retrying on CPU."
            )
            device = torch.device("cpu")
            bundle = load_vsc_model(checkpoint_path, device)
        else:
            raise

    _MODEL_CACHE[cache_key] = bundle
    return bundle


# =============================================================================
# Preprocessing: image transform + face crop (notebook cell 16, verbatim)
# =============================================================================

def _build_image_transform():
    return transforms.Compose(
        [
            transforms.Resize((CFG.image_size, CFG.image_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )


IMAGE_TRANSFORM = _build_image_transform() if transforms is not None else None


def center_crop_resize(rgb: np.ndarray, image_size: int) -> np.ndarray:
    height, width = rgb.shape[:2]
    side = min(height, width)

    y_start = (height - side) // 2
    x_start = (width - side) // 2

    crop = rgb[y_start:y_start + side, x_start:x_start + side]

    return cv2.resize(crop, (image_size, image_size), interpolation=cv2.INTER_LINEAR)


def crop_largest_face(
    rgb: np.ndarray,
    detector,
    image_size: int,
    margin_ratio: float,
    minimum_probability: float,
) -> Tuple[np.ndarray, bool]:
    boxes, probabilities = detector.detect(rgb)

    if boxes is None or probabilities is None:
        return center_crop_resize(rgb, image_size), False

    valid_indices = [
        index
        for index, probability in enumerate(probabilities)
        if probability is not None and float(probability) >= minimum_probability
    ]

    if not valid_indices:
        return center_crop_resize(rgb, image_size), False

    def box_area(index: int) -> float:
        x1, y1, x2, y2 = boxes[index]
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    largest_index = max(valid_indices, key=box_area)

    x1, y1, x2, y2 = boxes[largest_index]

    face_width = x2 - x1
    face_height = y2 - y1

    margin_x = face_width * margin_ratio
    margin_y = face_height * margin_ratio

    frame_height, frame_width = rgb.shape[:2]

    x1 = max(0, int(round(x1 - margin_x)))
    y1 = max(0, int(round(y1 - margin_y)))
    x2 = min(frame_width, int(round(x2 + margin_x)))
    y2 = min(frame_height, int(round(y2 + margin_y)))

    if x2 <= x1 or y2 <= y1:
        return center_crop_resize(rgb, image_size), False

    face = rgb[y1:y2, x1:x2]
    face = cv2.resize(face, (image_size, image_size), interpolation=cv2.INTER_LINEAR)

    return face, True


def jpeg_roundtrip_to_pil(face_rgb: np.ndarray, quality: int = 95) -> "Image.Image":
    face_rgb = np.ascontiguousarray(np.clip(face_rgb, 0, 255).astype(np.uint8))

    face_bgr = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR)

    success, encoded = cv2.imencode(".jpg", face_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])

    if not success:
        raise RuntimeError("Failed to JPEG-encode frame.")

    decoded_bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    if decoded_bgr is None:
        raise RuntimeError("Failed to decode frame.")

    decoded_rgb = cv2.cvtColor(decoded_bgr, cv2.COLOR_BGR2RGB)

    return Image.fromarray(decoded_rgb)


# =============================================================================
# Video windowing + frame sampling (notebook cell 31, verbatim)
# =============================================================================

def get_video_information(video_path: str) -> Dict[str, float]:
    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        raise VideoUnreadableError(f"Could not open video: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    capture.release()

    if fps <= 0:
        raise VideoUnreadableError("Could not read the video's FPS.")

    if total_frames <= 0:
        raise VideoUnreadableError("Video contains no readable frames.")

    duration_seconds = total_frames / fps

    return {
        "fps": fps,
        "total_frames": total_frames,
        "duration_seconds": duration_seconds,
    }


def build_temporal_windows(
    duration_seconds: float,
    window_seconds: float,
    stride_seconds: float,
    minimum_last_window_seconds: float,
) -> List[Tuple[float, float]]:
    if duration_seconds <= 0:
        return []

    # A short video is treated as a single window.
    if duration_seconds <= window_seconds:
        return [(0.0, duration_seconds)]

    windows = []
    start_time = 0.0

    while start_time < duration_seconds:
        end_time = min(start_time + window_seconds, duration_seconds)

        actual_length = end_time - start_time

        if actual_length >= minimum_last_window_seconds:
            windows.append((start_time, end_time))

        if end_time >= duration_seconds:
            break

        start_time += stride_seconds

    return windows


def read_window_frames(
    capture,
    fps: float,
    total_frames: int,
    start_seconds: float,
    end_seconds: float,
    num_frames: int,
) -> Tuple[List[np.ndarray], List[int]]:
    start_frame = max(0, int(round(start_seconds * fps)))

    end_frame = min(
        total_frames - 1,
        max(start_frame, int(round(end_seconds * fps)) - 1),
    )

    selected_indices = np.linspace(start_frame, end_frame, num_frames).round().astype(int)

    frames = []

    for frame_index in selected_indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))

        success, bgr = capture.read()

        if not success:
            continue

        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    if not frames:
        raise InsufficientFramesError(
            f"Could not read window {start_seconds:.2f}-{end_seconds:.2f}s."
        )

    while len(frames) < num_frames:
        frames.append(frames[-1].copy())

    return frames[:num_frames], selected_indices.tolist()


def prepare_window_tensor(
    raw_frames: Sequence[np.ndarray],
    detector,
    device: torch.device,
) -> Tuple[torch.Tensor, int]:
    frame_tensors = []
    faces_detected = 0

    for rgb_frame in raw_frames:
        face_rgb, detected = crop_largest_face(
            rgb=rgb_frame,
            detector=detector,
            image_size=CFG.image_size,
            margin_ratio=CFG.face_margin,
            minimum_probability=CFG.min_face_probability,
        )

        if detected:
            faces_detected += 1

        face_image = jpeg_roundtrip_to_pil(face_rgb, quality=95)

        frame_tensors.append(IMAGE_TRANSFORM(face_image))

    window_tensor = torch.stack(frame_tensors, dim=0).unsqueeze(0)
    window_tensor = window_tensor.to(device, dtype=torch.float32)

    return window_tensor, faces_detected


# =============================================================================
# Per-window inference (notebook cell 33, verbatim)
# =============================================================================

@torch.inference_mode()
def analyze_emotion_windows(
    video_path: str,
    model: nn.Module,
    classes: List[str],
    device: torch.device,
    analysis_config: VisualConfidenceConfig = VISUAL_CFG,
) -> pd.DataFrame:
    analysis_config.validate()

    if not os.path.isfile(video_path):
        raise VideoNotFoundError(f"Video not found: {video_path}")

    video_info = get_video_information(video_path)

    windows = build_temporal_windows(
        duration_seconds=video_info["duration_seconds"],
        window_seconds=analysis_config.window_seconds,
        stride_seconds=analysis_config.stride_seconds,
        minimum_last_window_seconds=analysis_config.minimum_last_window_seconds,
    )

    if not windows:
        raise InsufficientFramesError("No temporal windows could be built for this video.")

    if MTCNN is None:
        raise MissingDependencyError(
            f"facenet-pytorch is required but not installed: {_MTCNN_IMPORT_ERROR}"
        )

    detector = MTCNN(
        keep_all=True,
        min_face_size=40,
        post_process=False,
        device=device,
    )

    capture = cv2.VideoCapture(video_path)

    if not capture.isOpened():
        raise VideoUnreadableError(f"Could not open video: {video_path}")

    records = []

    try:
        for window_index, (start_seconds, end_seconds) in enumerate(windows):
            raw_frames, frame_indices = read_window_frames(
                capture=capture,
                fps=video_info["fps"],
                total_frames=int(video_info["total_frames"]),
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                num_frames=CFG.num_frames,
            )

            window_tensor, faces_detected = prepare_window_tensor(
                raw_frames=raw_frames,
                detector=detector,
                device=device,
            )

            logits = model(window_tensor)

            probability_array = torch.softmax(logits, dim=1)[0].float().cpu().numpy()

            predicted_index = int(probability_array.argmax())

            record = {
                "window_index": window_index,
                "start_seconds": float(start_seconds),
                "end_seconds": float(end_seconds),
                "mid_seconds": float((start_seconds + end_seconds) / 2.0),
                "duration_seconds": float(end_seconds - start_seconds),
                "dominant_emotion": classes[predicted_index],
                "model_top1_probability": float(probability_array[predicted_index]),
                "faces_detected": int(faces_detected),
                "face_detection_ratio": float(faces_detected / CFG.num_frames),
                "frame_indices": frame_indices,
            }

            for emotion, probability in zip(classes, probability_array):
                record[f"prob_{emotion}"] = float(probability)

            records.append(record)

    finally:
        capture.release()

    return pd.DataFrame(records)


# =============================================================================
# Temporal metrics (notebook cell 35, verbatim)
# =============================================================================

def probability_matrix_from_windows(windows_df: pd.DataFrame, classes: List[str]) -> np.ndarray:
    columns = [f"prob_{emotion}" for emotion in classes]
    return windows_df[columns].to_numpy(dtype=np.float64)


def calculate_emotion_stability(windows_df: pd.DataFrame, classes: List[str]) -> Dict[str, float]:
    probability_matrix = probability_matrix_from_windows(windows_df, classes)

    if len(probability_matrix) <= 1:
        return {"emotion_stability": 1.0, "mean_transition_distance": 0.0}

    # Total Variation Distance between 0 and 1.
    transition_distances = 0.5 * np.abs(
        probability_matrix[1:] - probability_matrix[:-1]
    ).sum(axis=1)

    mean_transition_distance = float(transition_distances.mean())

    stability = float(np.clip(1.0 - mean_transition_distance, 0.0, 1.0))

    return {
        "emotion_stability": stability,
        "mean_transition_distance": mean_transition_distance,
    }


def longest_true_streak(values: Sequence[bool]) -> int:
    longest = 0
    current = 0

    for value in values:
        if bool(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def negative_affect_probabilities_from_windows(
    windows_df: pd.DataFrame,
    sad_weight: float,
    disgust_weight: float,
    fearful_weight: float,
    angry_weight: float,
) -> np.ndarray:
    # Raw sum (not average) — see notebook cell 29/36 rationale: these four
    # probabilities are part of one softmax distribution over 8 classes, so
    # weighted-averaging with weights summing to 1.0 would dilute a strong
    # single signal (e.g. disgust 96%) just because it's divided by 4.
    negative_affect = (
        sad_weight * windows_df["prob_sad"].to_numpy(dtype=np.float64)
        + disgust_weight * windows_df["prob_disgust"].to_numpy(dtype=np.float64)
        + fearful_weight * windows_df["prob_fearful"].to_numpy(dtype=np.float64)
        + angry_weight * windows_df["prob_angry"].to_numpy(dtype=np.float64)
    )

    return np.clip(negative_affect, 0.0, 1.0)


def calculate_negative_affect_persistence(
    windows_df: pd.DataFrame,
    threshold: float,
    sad_weight: float,
    disgust_weight: float,
    fearful_weight: float,
    angry_weight: float,
) -> Dict[str, float]:
    negative_affect_probabilities = negative_affect_probabilities_from_windows(
        windows_df=windows_df,
        sad_weight=sad_weight,
        disgust_weight=disgust_weight,
        fearful_weight=fearful_weight,
        angry_weight=angry_weight,
    )

    high_negative_affect_windows = negative_affect_probabilities >= threshold

    negative_affect_mean = float(negative_affect_probabilities.mean())

    high_negative_affect_ratio = float(high_negative_affect_windows.mean())

    longest_streak = longest_true_streak(high_negative_affect_windows)

    longest_streak_ratio = float(longest_streak / max(len(high_negative_affect_windows), 1))

    negative_affect_persistence = float(
        np.clip(
            0.50 * negative_affect_mean
            + 0.25 * high_negative_affect_ratio
            + 0.25 * longest_streak_ratio,
            0.0,
            1.0,
        )
    )

    return {
        "negative_affect_persistence": negative_affect_persistence,
        "mean_negative_affect_probability": negative_affect_mean,
        "high_negative_affect_window_ratio": high_negative_affect_ratio,
        "longest_negative_affect_streak_windows": int(longest_streak),
        "longest_negative_affect_streak_ratio": longest_streak_ratio,
    }


def negative_affect_episode_start_indices(
    negative_affect_probabilities: np.ndarray,
    threshold: float,
) -> List[int]:
    is_high = negative_affect_probabilities >= threshold

    starts = []

    for index, value in enumerate(is_high):
        previous = bool(is_high[index - 1]) if index > 0 else False

        if bool(value) and not previous:
            starts.append(index)

    return starts


def calculate_calm_recovery(
    windows_df: pd.DataFrame,
    negative_affect_threshold: float,
    sad_weight: float,
    disgust_weight: float,
    fearful_weight: float,
    angry_weight: float,
    recovery_horizon_windows: int,
    recovery_minimum_signal: float,
    recovery_minimum_gain: float,
) -> Dict[str, object]:
    negative_affect = negative_affect_probabilities_from_windows(
        windows_df=windows_df,
        sad_weight=sad_weight,
        disgust_weight=disgust_weight,
        fearful_weight=fearful_weight,
        angry_weight=angry_weight,
    )

    calm = windows_df["prob_calm"].to_numpy(dtype=np.float64)
    neutral = windows_df["prob_neutral"].to_numpy(dtype=np.float64)

    # Neutral counts at half weight since it isn't explicit calm.
    calm_signal = calm + 0.5 * neutral

    episode_starts = negative_affect_episode_start_indices(
        negative_affect_probabilities=negative_affect,
        threshold=negative_affect_threshold,
    )

    if not episode_starts:
        return {
            "calm_recovery": 1.0,
            "negative_affect_episode_count": 0,
            "recovered_episode_count": 0,
            "recovery_events": [],
            "recovery_note": "No negative-affect episode required recovery.",
        }

    recovery_events = []
    recovered_count = 0

    for start_index in episode_starts:
        future_start = start_index + 1
        future_end = min(len(windows_df), start_index + 1 + recovery_horizon_windows)

        recovered = False
        recovery_index = None

        if future_start < future_end:
            baseline_calm_signal = float(calm_signal[start_index])
            starting_negative_affect = float(negative_affect[start_index])

            for candidate_index in range(future_start, future_end):
                signal_gain = float(calm_signal[candidate_index] - baseline_calm_signal)

                candidate_recovered = (
                    calm_signal[candidate_index] >= recovery_minimum_signal
                    and signal_gain >= recovery_minimum_gain
                    and negative_affect[candidate_index] < starting_negative_affect
                )

                if candidate_recovered:
                    recovered = True
                    recovery_index = candidate_index
                    recovered_count += 1
                    break

        recovery_events.append(
            {
                "negative_affect_start_window": int(start_index),
                "recovered": bool(recovered),
                "recovery_window": int(recovery_index) if recovery_index is not None else None,
            }
        )

    recovery_score = float(recovered_count / len(episode_starts))

    return {
        "calm_recovery": recovery_score,
        "negative_affect_episode_count": int(len(episode_starts)),
        "recovered_episode_count": int(recovered_count),
        "recovery_events": recovery_events,
        "recovery_note": None,
    }


# =============================================================================
# Visual Behavioral Confidence Score (notebook cell 37, verbatim)
# =============================================================================

def calculate_comfort_signal(
    windows_df: pd.DataFrame,
    calm_weight: float,
    neutral_weight: float,
    happy_weight: float,
) -> Dict[str, float]:
    mean_calm = float(windows_df["prob_calm"].mean())
    mean_neutral = float(windows_df["prob_neutral"].mean())
    mean_happy = float(windows_df["prob_happy"].mean())

    comfort = float(
        np.clip(
            calm_weight * mean_calm + neutral_weight * mean_neutral + happy_weight * mean_happy,
            0.0,
            1.0,
        )
    )

    return {
        "comfort_signal": comfort,
        "mean_calm_probability": mean_calm,
        "mean_neutral_probability": mean_neutral,
        "mean_happy_probability": mean_happy,
    }


def calculate_visual_reliability(
    windows_df: pd.DataFrame,
    minimum_windows: int,
) -> Dict[str, float]:
    face_detection_ratio = float(windows_df["face_detection_ratio"].mean())

    window_coverage = float(min(len(windows_df) / max(minimum_windows, 1), 1.0))

    reliability = float(
        np.clip(0.80 * face_detection_ratio + 0.20 * window_coverage, 0.0, 1.0)
    )

    return {
        "visual_reliability": reliability,
        "mean_face_detection_ratio": face_detection_ratio,
        "window_coverage": window_coverage,
    }


def visual_confidence_level(score: float, sufficient_evidence: bool) -> str:
    if not sufficient_evidence:
        return "insufficient_evidence"

    if score >= 75.0:
        return "high"

    if score >= 50.0:
        return "moderate"

    return "low"


def calculate_visual_confidence_summary(
    windows_df: pd.DataFrame,
    classes: List[str],
    analysis_config: VisualConfidenceConfig = VISUAL_CFG,
) -> Dict[str, object]:
    if windows_df.empty:
        raise InsufficientFramesError("windows_df is empty.")

    stability = calculate_emotion_stability(windows_df, classes)

    negative_affect = calculate_negative_affect_persistence(
        windows_df=windows_df,
        threshold=analysis_config.negative_affect_threshold,
        sad_weight=analysis_config.sad_weight,
        disgust_weight=analysis_config.disgust_weight,
        fearful_weight=analysis_config.fearful_weight,
        angry_weight=analysis_config.angry_weight,
    )

    recovery = calculate_calm_recovery(
        windows_df=windows_df,
        negative_affect_threshold=analysis_config.negative_affect_threshold,
        sad_weight=analysis_config.sad_weight,
        disgust_weight=analysis_config.disgust_weight,
        fearful_weight=analysis_config.fearful_weight,
        angry_weight=analysis_config.angry_weight,
        recovery_horizon_windows=analysis_config.recovery_horizon_windows,
        recovery_minimum_signal=analysis_config.recovery_minimum_signal,
        recovery_minimum_gain=analysis_config.recovery_minimum_gain,
    )

    comfort = calculate_comfort_signal(
        windows_df=windows_df,
        calm_weight=analysis_config.calm_weight,
        neutral_weight=analysis_config.neutral_weight,
        happy_weight=analysis_config.happy_weight,
    )

    reliability = calculate_visual_reliability(
        windows_df=windows_df,
        minimum_windows=analysis_config.minimum_windows_for_decision,
    )

    # --- Base score (fully linear, no gated penalty) ---
    base_score_0_to_1 = (
        analysis_config.comfort_weight * comfort["comfort_signal"]
        + analysis_config.stability_weight * stability["emotion_stability"]
        + analysis_config.recovery_weight * recovery["calm_recovery"]
        + analysis_config.negative_affect_weight
        * (1.0 - negative_affect["negative_affect_persistence"])
    )

    visual_score = float(np.clip(base_score_0_to_1 * 100.0, 0.0, 100.0))

    # --- Confidence interval (built on visual reliability) ---
    confidence_margin = float(
        (1.0 - reliability["visual_reliability"]) * analysis_config.confidence_interval_max_margin
    )

    score_low = float(np.clip(visual_score - confidence_margin, 0.0, 100.0))
    score_high = float(np.clip(visual_score + confidence_margin, 0.0, 100.0))

    enough_windows = len(windows_df) >= analysis_config.minimum_windows_for_decision

    enough_faces = (
        reliability["mean_face_detection_ratio"] >= analysis_config.minimum_face_detection_ratio
    )

    sufficient_evidence = bool(enough_windows and enough_faces)

    level = visual_confidence_level(score=visual_score, sufficient_evidence=sufficient_evidence)

    summary = {
        "visual_behavioral_confidence_score": visual_score,
        "confidence_margin": confidence_margin,
        "score_range": {"low": score_low, "high": score_high},
        "visual_confidence_level": level,
        "sufficient_evidence": sufficient_evidence,
        "number_of_windows": int(len(windows_df)),
        "evidence_checks": {
            "enough_windows": bool(enough_windows),
            "enough_faces": bool(enough_faces),
        },
        "metrics": {
            **comfort,
            **stability,
            **negative_affect,
            **recovery,
            **reliability,
        },
        "formula_weights": {
            "comfort_signal": analysis_config.comfort_weight,
            "emotion_stability": analysis_config.stability_weight,
            "calm_recovery": analysis_config.recovery_weight,
            "low_negative_affect": analysis_config.negative_affect_weight,
        },
        "interpretation": (
            "Behavioral confidence indicators observed during this video; "
            "not a personality judgment. Score is reported as a range to "
            "reflect measurement uncertainty from visual reliability."
        ),
    }

    return summary


# =============================================================================
# Public entry point
# =============================================================================

def analyze_visual_confidence(video_path: str) -> Dict[str, object]:
    """
    Run the full VSC visual-confidence pipeline on a local video file.

    Ports notebook cells 31/33/35/37/41 (temporal windowing, per-window
    emotion inference, stability/negative-affect/recovery/comfort metrics,
    and the final visual-behavioral-confidence-score calculation).

    Always returns a JSON-serializable dict; never raises for expected
    failure modes (missing/unreadable video, missing/incompatible
    checkpoint, missing dependency, no detected face, insufficient frames,
    CUDA failure) — those are reported via "status", "warnings", and
    "error" instead.
    """

    start_time = time.time()
    warnings_list: List[str] = []

    labels_match = _labels_json_matches_model_classes()
    if labels_match is False:
        warnings_list.append(
            "labels.json class order does not match the hardcoded MODEL_CLASSES; "
            "using MODEL_CLASSES (the notebook's source of truth)."
        )

    result: Dict[str, object] = {
        "status": "failed",
        "predicted_emotion": None,
        "confidence": 0.0,
        "emotion_probabilities": {},
        "visual_behavioral_confidence_score": 0.0,
        "visual_confidence_level": "insufficient_evidence",
        "sufficient_evidence": False,
        "number_of_windows": 0,
        "metrics": {},
        "warnings": warnings_list,
        "processing_time_seconds": 0.0,
        "device": "cpu",
        "windows": [],
        "error": None,
    }

    try:
        video_file = Path(video_path)
        if not video_file.is_file():
            raise VideoNotFoundError(f"Video file not found: {video_path}")

        device = _select_device(warnings_list)
        result["device"] = device.type

        model, classes, checkpoint_metadata, device = get_model(
            checkpoint_path=DEFAULT_CHECKPOINT_PATH,
            device=device,
            warnings_out=warnings_list,
        )
        result["device"] = device.type

        windows_df = analyze_emotion_windows(
            video_path=str(video_file),
            model=model,
            classes=classes,
            device=device,
            analysis_config=VISUAL_CFG,
        )

        summary = calculate_visual_confidence_summary(
            windows_df=windows_df,
            classes=classes,
            analysis_config=VISUAL_CFG,
        )

        # Aggregate per-window probabilities (already computed by the
        # notebook's own analyze_emotion_windows) into a single overall
        # prediction. This is a mean-pooling aggregation of existing
        # per-window model outputs, not new model logic.
        probability_columns = [f"prob_{emotion}" for emotion in classes]
        mean_probabilities = windows_df[probability_columns].mean(axis=0)
        emotion_probabilities = {
            emotion: float(mean_probabilities[f"prob_{emotion}"]) for emotion in classes
        }
        predicted_emotion = max(emotion_probabilities, key=emotion_probabilities.get)
        confidence = float(emotion_probabilities[predicted_emotion])

        mean_face_ratio = summary["metrics"]["mean_face_detection_ratio"]
        if mean_face_ratio == 0.0:
            warnings_list.append(
                "No face was detected in any sampled frame; used center-crop "
                "fallback for the entire video."
            )
        elif mean_face_ratio < VISUAL_CFG.minimum_face_detection_ratio:
            warnings_list.append(
                f"Face detection ratio ({mean_face_ratio:.2f}) is below the "
                f"reliability threshold ({VISUAL_CFG.minimum_face_detection_ratio})."
            )

        status = "ok" if summary["sufficient_evidence"] else "insufficient_evidence"

        windows_records = windows_df.to_dict(orient="records")

        result.update(
            {
                "status": status,
                "predicted_emotion": predicted_emotion,
                "confidence": confidence,
                "emotion_probabilities": emotion_probabilities,
                "visual_behavioral_confidence_score": summary[
                    "visual_behavioral_confidence_score"
                ],
                "score_range": summary["score_range"],
                "confidence_margin": summary["confidence_margin"],
                "visual_confidence_level": summary["visual_confidence_level"],
                "sufficient_evidence": summary["sufficient_evidence"],
                "number_of_windows": summary["number_of_windows"],
                "metrics": summary["metrics"],
                "formula_weights": summary["formula_weights"],
                "interpretation": summary["interpretation"],
                "warnings": warnings_list,
                "device": device.type,
                "windows": windows_records,
                "checkpoint_metadata": checkpoint_metadata,
                "error": None,
            }
        )

    except VisionModuleError as error:
        result["error"] = f"{type(error).__name__}: {error}"
        warnings_list.append(result["error"])
        result["status"] = "failed"
    except Exception as error:  # noqa: BLE001 - top-level safety net
        result["error"] = f"{type(error).__name__}: {error}"
        warnings_list.append(result["error"])
        result["status"] = "failed"
    finally:
        result["processing_time_seconds"] = round(time.time() - start_time, 4)
        result["warnings"] = warnings_list

    return result
