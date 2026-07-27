"""
Create a complete reproducibility/archive package for:
vsc_ravdess_lora_r16_test73_24.pt

Run inside Kaggle after editing the paths in the USER SETTINGS section.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import torch


# =============================================================================
# USER SETTINGS
# =============================================================================


MODEL_NAME = "vsc_ravdess_lora_r16_test73_24"

BASE_DIR = Path(__file__).resolve().parent

CANONICAL_CHECKPOINT = (
    BASE_DIR
    / "vsc_ravdess_test73_deployment (1)"
    / "vsc_ravdess_lora_r16_test73_24.pt"
)

# Optional original checkpoint before export. Set to None to skip.
SOURCE_CHECKPOINT: Optional[Path] = None

OUTPUT_ROOT = BASE_DIR
PACKAGE_DIR = OUTPUT_ROOT / f"{MODEL_NAME}_complete_package"
ZIP_PATH = OUTPUT_ROOT / f"{MODEL_NAME}_complete_package.zip"

# Add exact source notebooks/scripts here when they exist on disk.
# Kaggle does not always expose the currently open notebook as an .ipynb file,
# so download/save that notebook separately or attach it as a Dataset first.
SOURCE_FILES = [
    Path("/kaggle/working/VSC_RAVDESS_LoRA_R16_Test73_Inference.ipynb"),
    Path("/kaggle/working/vsc_ravdess_lora_r16_best.py"),
    Path("/kaggle/working/vsc_ravdess_lora_r16_best.ipynb"),
]

# Metadata/evaluation files. Missing files are skipped safely.
DATA_AND_REPORT_FILES = [
    Path("/kaggle/working/processed_ravdess.csv"),
    Path("/kaggle/working/ravdess_metadata.csv"),
    Path("/kaggle/working/ravdess_balanced.csv"),
    Path("/kaggle/working/classification_report.txt"),
    Path("/kaggle/working/confusion_matrix.csv"),
    Path("/kaggle/working/evaluation_results.json"),
    Path("/kaggle/working/test_results.json"),
]

# Candidate processed-frame folders.
FRAMES_DIR_CANDIDATES = [
    Path("/kaggle/working/processed_frames_ravdess"),
    Path("/kaggle/working/processed_ravdess"),
    Path("/kaggle/working/processed_frames"),
]

# "full"   = copy the entire processed-frame directory.
# "sample" = copy a small representative sample + full file manifest.
# "none"   = do not copy images; save only the manifest when a folder is found.
FRAMES_MODE = "sample"

SAMPLE_CLIPS_PER_CLASS = 2
COMPUTE_FRAME_HASHES = False

INCLUDE_FULL_PIP_FREEZE = True
OVERWRITE_EXISTING_PACKAGE = True


# =============================================================================
# MODEL FACTS
# =============================================================================

EXPECTED_CLASSES = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

MODEL_FACTS = {
    "model_name": MODEL_NAME,
    "task": "RAVDESS visual emotion classification",
    "epoch": 11,
    "validation_accuracy": 0.7387820512820513,
    "test_accuracy": 0.7324,
    "weighted_f1": 0.7229,
    "macro_f1": 0.6885,
    "classes": EXPECTED_CLASSES,
    "input_shape": [1, 16, 3, 224, 224],
    "architecture": {
        "backbone": "torchvision Swin Transformer Tiny",
        "lora_rank": 16,
        "lora_alpha": 32,
        "lora_targets": "12 ShiftedWindowAttention qkv layers",
        "temporal_model": "TCN",
        "tcn_channels": [256, 256, 256],
        "tcn_dilations": [1, 2, 4],
        "aggregation": "Temporal Attention",
    },
    "preprocessing": {
        "num_frames": 16,
        "sampling": "uniform sampling over the complete video",
        "face_detector": "MTCNN",
        "face_selection": "largest detected face",
        "face_margin_ratio": 0.10,
        "image_size": 224,
        "jpeg_roundtrip": True,
        "normalization_mean": [0.485, 0.456, 0.406],
        "normalization_std": [0.229, 0.224, 0.225],
    },
    "split": {
        "train_actors": "1-18",
        "validation_actors": "19-21",
        "test_actors": "22-24",
        "test_items": 624,
    },
}


# =============================================================================
# HELPERS
# =============================================================================

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def human_size(size_bytes: int) -> str:
    value = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


def copy_file_if_exists(
    source: Optional[Path],
    destination_directory: Path,
    destination_name: Optional[str] = None,
) -> Optional[Path]:
    if source is None or not source.is_file():
        print(f"⚠️ Skipped missing file: {source}")
        return None

    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / (destination_name or source.name)
    shutil.copy2(source, destination)
    print(f"✅ Copied: {source} -> {destination}")
    return destination


def package_versions() -> dict[str, str]:
    distribution_names = [
        "torch",
        "torchvision",
        "facenet-pytorch",
        "opencv-python",
        "numpy",
        "pandas",
        "Pillow",
        "matplotlib",
        "scikit-learn",
        "tqdm",
    ]

    versions: dict[str, str] = {}

    for distribution in distribution_names:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"

    return versions


def write_minimal_requirements(path: Path, versions: dict[str, str]) -> None:
    preferred_order = [
        "torch",
        "torchvision",
        "facenet-pytorch",
        "opencv-python",
        "numpy",
        "pandas",
        "Pillow",
        "matplotlib",
        "scikit-learn",
        "tqdm",
    ]

    lines = []
    for name in preferred_order:
        version = versions.get(name, "not-installed")
        if version != "not-installed":
            lines.append(f"{name}=={version}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_frames_directory() -> Optional[Path]:
    for candidate in FRAMES_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate

    # Lightweight automatic detection inside /kaggle/working.
    root = Path("/kaggle/working")
    if not root.exists():
        return None

    for current_root, directories, files in os.walk(root):
        current = Path(current_root)

        # Avoid walking into the package currently being created.
        if PACKAGE_DIR in current.parents or current == PACKAGE_DIR:
            directories[:] = []
            continue

        jpg_count = sum(
            1 for filename in files
            if filename.lower().endswith((".jpg", ".jpeg", ".png"))
        )

        if jpg_count >= 8:
            return current.parent if current.name.startswith("Actor_") else current

    return None


def iter_image_files(frames_root: Path) -> Iterable[Path]:
    for extension in ("*.jpg", "*.jpeg", "*.png"):
        yield from frames_root.rglob(extension)


def write_frames_manifest(
    frames_root: Path,
    output_csv: Path,
    compute_hashes: bool,
) -> tuple[int, int]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_size = 0

    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "relative_path",
                "size_bytes",
                "sha256",
            ],
        )
        writer.writeheader()

        for image_path in iter_image_files(frames_root):
            size = image_path.stat().st_size
            relative_path = image_path.relative_to(frames_root)

            writer.writerow({
                "relative_path": str(relative_path),
                "size_bytes": size,
                "sha256": (
                    sha256_file(image_path)
                    if compute_hashes
                    else ""
                ),
            })

            file_count += 1
            total_size += size

    return file_count, total_size


def copy_frame_sample(
    frames_root: Path,
    destination_root: Path,
    clips_per_class: int,
) -> int:
    destination_root.mkdir(parents=True, exist_ok=True)

    # Prefer class directories. Fall back to the first clip directories found.
    class_directories = [
        path for path in frames_root.iterdir()
        if path.is_dir()
    ]

    copied_clip_count = 0

    for class_directory in sorted(class_directories):
        clip_directories = [
            path for path in class_directory.iterdir()
            if path.is_dir()
        ]

        # Some layouts store images directly under a class directory.
        if not clip_directories:
            image_files = list(iter_image_files(class_directory))
            if image_files:
                destination = destination_root / class_directory.name
                destination.mkdir(parents=True, exist_ok=True)
                for image_path in sorted(image_files)[:16]:
                    shutil.copy2(image_path, destination / image_path.name)
                copied_clip_count += 1
            continue

        for clip_directory in sorted(clip_directories)[:clips_per_class]:
            relative = clip_directory.relative_to(frames_root)
            destination = destination_root / relative
            shutil.copytree(
                clip_directory,
                destination,
                dirs_exist_ok=True,
            )
            copied_clip_count += 1

    if copied_clip_count == 0:
        # Generic fallback: copy the first directories containing images.
        seen_parents: set[Path] = set()
        for image_path in iter_image_files(frames_root):
            parent = image_path.parent
            if parent in seen_parents:
                continue
            seen_parents.add(parent)

            relative = parent.relative_to(frames_root)
            destination = destination_root / relative
            shutil.copytree(parent, destination, dirs_exist_ok=True)
            copied_clip_count += 1

            if copied_clip_count >= clips_per_class * 8:
                break

    return copied_clip_count


def checkpoint_summary(checkpoint_path: Path) -> dict:
    try:
        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
            weights_only=False,
        )
    except TypeError:
        checkpoint = torch.load(
            checkpoint_path,
            map_location="cpu",
        )

    if isinstance(checkpoint, dict):
        state_dict = checkpoint.get("model_state", checkpoint)
        metadata = {
            key: value
            for key, value in checkpoint.items()
            if key != "model_state"
            and isinstance(
                value,
                (str, int, float, bool, list, tuple, dict, type(None)),
            )
        }
    else:
        state_dict = checkpoint
        metadata = {}

    if not isinstance(state_dict, dict):
        raise TypeError("Checkpoint state_dict is not a dictionary.")

    first_key = next(iter(state_dict))
    tensor_count = sum(
        1 for value in state_dict.values()
        if torch.is_tensor(value)
    )
    parameter_count = sum(
        int(value.numel())
        for value in state_dict.values()
        if torch.is_tensor(value)
    )

    return {
        "file_name": checkpoint_path.name,
        "file_size_bytes": checkpoint_path.stat().st_size,
        "sha256": sha256_file(checkpoint_path),
        "first_key": first_key,
        "state_tensor_count": tensor_count,
        "state_parameter_count": parameter_count,
        "checkpoint_metadata": metadata,
    }


def write_model_card(path: Path, canonical_summary: dict) -> None:
    text = f"""# {MODEL_NAME}

## Purpose

Visual emotion classification for the InterviewIQ visual module.

## Canonical checkpoint

- File: `{canonical_summary["file_name"]}`
- SHA-256: `{canonical_summary["sha256"]}`
- Size: `{human_size(canonical_summary["file_size_bytes"])}`
- Epoch: 11
- Validation accuracy: 73.88%
- Test accuracy: 73.24%
- Weighted F1: 72.29%
- Macro F1: 68.85%

## Class order

```python
{EXPECTED_CLASSES}
```

The class order must not be changed.

## Architecture

- Torchvision Swin Transformer Tiny.
- LoRA rank 16, alpha 32.
- LoRA injected into 12 `qkv` attention layers.
- TCN channels `[256, 256, 256]`.
- TCN dilations `[1, 2, 4]`.
- Temporal attention aggregation.
- Eight emotion classes.

## Input and preprocessing

- Input shape: `[batch, 16, 3, 224, 224]`.
- Select 16 frames uniformly across the complete video.
- Use MTCNN and select the largest detected face.
- Add a 10% face margin.
- Resize to 224×224.
- Apply a JPEG save/read round trip.
- Apply ImageNet normalization.

## Intended use

This model predicts visible emotion signals. It must not independently decide
whether a person is confident, suitable for employment, truthful, depressed,
or psychologically healthy.

## Reproducibility

See:

- `config/config.json`
- `config/labels.json`
- `environment/requirements.txt`
- `environment/environment_freeze.txt`
- `manifests/package_manifest.csv`
- `manifests/frames_manifest.csv`
- `reports/checkpoint_summary.json`
"""
    path.write_text(text, encoding="utf-8")


def write_package_manifest(package_dir: Path, output_csv: Path) -> None:
    rows = []

    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or path == output_csv:
            continue

        rows.append({
            "relative_path": str(path.relative_to(package_dir)),
            "size_bytes": path.stat().st_size,
            "size_human": human_size(path.stat().st_size),
            "sha256": sha256_file(path),
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "relative_path",
                "size_bytes",
                "size_human",
                "sha256",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


# =============================================================================
# BUILD PACKAGE
# =============================================================================

def main() -> None:
    if FRAMES_MODE not in {"full", "sample", "none"}:
        raise ValueError(
            "FRAMES_MODE must be one of: full, sample, none."
        )

    if not CANONICAL_CHECKPOINT.is_file():
        raise FileNotFoundError(
            f"Canonical checkpoint not found:\n{CANONICAL_CHECKPOINT}"
        )

    if PACKAGE_DIR.exists():
        if OVERWRITE_EXISTING_PACKAGE:
            shutil.rmtree(PACKAGE_DIR)
        else:
            raise FileExistsError(
                f"Package already exists:\n{PACKAGE_DIR}"
            )

    directories = {
        "checkpoints": PACKAGE_DIR / "checkpoints",
        "source": PACKAGE_DIR / "source",
        "config": PACKAGE_DIR / "config",
        "data": PACKAGE_DIR / "data",
        "reports": PACKAGE_DIR / "reports",
        "frames": PACKAGE_DIR / "frames",
        "environment": PACKAGE_DIR / "environment",
        "manifests": PACKAGE_DIR / "manifests",
    }

    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("BUILDING COMPLETE VSC MODEL PACKAGE")
    print("=" * 78)

    # 1. Checkpoints
    canonical_copy = copy_file_if_exists(
        CANONICAL_CHECKPOINT,
        directories["checkpoints"],
    )
    assert canonical_copy is not None

    source_copy = None
    if SOURCE_CHECKPOINT is not None:
        source_copy = copy_file_if_exists(
            SOURCE_CHECKPOINT,
            directories["checkpoints"],
            destination_name="source_training_checkpoint.pt",
        )

    canonical_summary = checkpoint_summary(canonical_copy)

    checkpoint_report = {
        "canonical_checkpoint": canonical_summary,
        "source_checkpoint": (
            checkpoint_summary(source_copy)
            if source_copy is not None
            else None
        ),
        "canonical_and_source_byte_identical": (
            sha256_file(canonical_copy)
            == sha256_file(source_copy)
            if source_copy is not None
            else None
        ),
    }

    (
        directories["reports"]
        / "checkpoint_summary.json"
    ).write_text(
        json.dumps(
            checkpoint_report,
            indent=4,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    # 2. Config and labels
    config_payload = dict(MODEL_FACTS)
    config_payload["archive_created_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    (
        directories["config"]
        / "config.json"
    ).write_text(
        json.dumps(
            config_payload,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (
        directories["config"]
        / "labels.json"
    ).write_text(
        json.dumps(
            {
                "classes": EXPECTED_CLASSES,
                "index_to_label": {
                    str(index): label
                    for index, label in enumerate(EXPECTED_CLASSES)
                },
                "label_to_index": {
                    label: index
                    for index, label in enumerate(EXPECTED_CLASSES)
                },
            },
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 3. Source code/notebooks
    for source_file in SOURCE_FILES:
        copy_file_if_exists(
            source_file,
            directories["source"],
        )

    # Also preserve the package script itself when __file__ is available.
    try:
        current_script = Path(__file__).resolve()
        if current_script.is_file():
            shutil.copy2(
                current_script,
                directories["source"] / current_script.name,
            )
    except NameError:
        pass

    # 4. Metadata and evaluation artifacts
    for artifact in DATA_AND_REPORT_FILES:
        destination = (
            directories["data"]
            if artifact.suffix.lower() == ".csv"
            else directories["reports"]
        )
        copy_file_if_exists(
            artifact,
            destination,
        )

    # 5. Environment
    versions = package_versions()

    (
        directories["environment"]
        / "package_versions.json"
    ).write_text(
        json.dumps(
            versions,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    write_minimal_requirements(
        directories["environment"] / "requirements.txt",
        versions,
    )

    environment_info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "cudnn_version": (
            torch.backends.cudnn.version()
            if torch.cuda.is_available()
            else None
        ),
        "gpu_name": (
            torch.cuda.get_device_name(0)
            if torch.cuda.is_available()
            else None
        ),
    }

    (
        directories["environment"]
        / "system_info.json"
    ).write_text(
        json.dumps(
            environment_info,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if INCLUDE_FULL_PIP_FREEZE:
        try:
            freeze = subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"],
                text=True,
            )
            (
                directories["environment"]
                / "environment_freeze.txt"
            ).write_text(
                freeze,
                encoding="utf-8",
            )
        except Exception as error:
            (
                directories["environment"]
                / "environment_freeze_error.txt"
            ).write_text(
                str(error),
                encoding="utf-8",
            )

    # 6. Frames
    frames_root = find_frames_directory()

    frames_report = {
        "frames_mode": FRAMES_MODE,
        "source_frames_directory": (
            str(frames_root)
            if frames_root is not None
            else None
        ),
        "file_count": 0,
        "total_size_bytes": 0,
        "sample_clips_copied": 0,
    }

    if frames_root is None:
        print("⚠️ No processed-frame directory was found.")
    else:
        print(f"📂 Frames directory: {frames_root}")

        frame_count, total_frame_size = write_frames_manifest(
            frames_root=frames_root,
            output_csv=(
                directories["manifests"]
                / "frames_manifest.csv"
            ),
            compute_hashes=COMPUTE_FRAME_HASHES,
        )

        frames_report["file_count"] = frame_count
        frames_report["total_size_bytes"] = total_frame_size

        print(
            f"Frames: {frame_count:,} files | "
            f"{human_size(total_frame_size)}"
        )

        if FRAMES_MODE == "full":
            destination = (
                directories["frames"]
                / "processed_frames_full"
            )
            shutil.copytree(
                frames_root,
                destination,
                dirs_exist_ok=True,
            )
            print("✅ Full frames directory copied.")

        elif FRAMES_MODE == "sample":
            copied_clips = copy_frame_sample(
                frames_root=frames_root,
                destination_root=(
                    directories["frames"]
                    / "processed_frames_sample"
                ),
                clips_per_class=SAMPLE_CLIPS_PER_CLASS,
            )
            frames_report[
                "sample_clips_copied"
            ] = copied_clips
            print(
                f"✅ Sample frame clips copied: {copied_clips}"
            )

        else:
            print(
                "ℹ️ Frames were not copied; manifest only."
            )

    (
        directories["reports"]
        / "frames_summary.json"
    ).write_text(
        json.dumps(
            frames_report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 7. Model card and archive notes
    write_model_card(
        PACKAGE_DIR / "MODEL_CARD.md",
        canonical_summary,
    )

    archive_readme = f"""# Complete archive for {MODEL_NAME}

Created at: {datetime.now(timezone.utc).isoformat()}

## Main folders

- checkpoints/: canonical and optional source checkpoints.
- source/: Python and notebook source files found on disk.
- config/: model architecture, preprocessing, classes and metrics.
- data/: metadata and split CSV files found on disk.
- reports/: checkpoint, evaluation and frame summaries.
- frames/: full or sampled processed frames depending on FRAMES_MODE.
- environment/: requirements, pip freeze and system/GPU information.
- manifests/: SHA-256 manifest for package files and frame inventory.

## Important

Kaggle may not expose the currently open notebook as an `.ipynb` file.
Download that notebook from Kaggle or save it as a Dataset, then add its exact
path to SOURCE_FILES and rerun this packaging script.
"""

    (
        PACKAGE_DIR
        / "README.md"
    ).write_text(
        archive_readme,
        encoding="utf-8",
    )

    # 8. Final package manifest
    write_package_manifest(
        package_dir=PACKAGE_DIR,
        output_csv=(
            directories["manifests"]
            / "package_manifest.csv"
        ),
    )

    # Regenerate manifest once so it includes the first manifest file itself
    # is intentionally avoided because a file cannot contain its own stable hash.

    # 9. Zip
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    archive_base = ZIP_PATH.with_suffix("")

    shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=PACKAGE_DIR.parent,
        base_dir=PACKAGE_DIR.name,
    )

    print("\n" + "=" * 78)
    print("✅ COMPLETE MODEL ARCHIVE CREATED")
    print("Folder:", PACKAGE_DIR)
    print("ZIP   :", ZIP_PATH)
    print("Size  :", human_size(ZIP_PATH.stat().st_size))
    print("=" * 78)


if __name__ == "__main__":
    main()
