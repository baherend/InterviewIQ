"""
config.py — Central configuration loader for the Interview IQ NLP module.

Responsibilities:
  - Load all six YAML configs from configs/ at construction time.
  - Expose each config as a typed property returning the raw dict.
  - Expose convenience shortcuts for the four pre-calibration hyperparameters
    (τ, τ_E, α, k) and the three model name strings.
  - Print (and log as WARNING) the PRE-CALIBRATION tag for every unvalidated
    hyperparameter on every load, so every run is auditable.

Usage:
    from interview_iq.config import Config
    cfg = Config()
    score = cfg.tau_e          # 0.9 (pre-calibration default)
    model = cfg.nli_model      # "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ── path resolution ────────────────────────────────────────────────────────────
# src/interview_iq/config.py → parent = interview_iq → parent = src → parent = repo root
_REPO_ROOT: Path = Path(__file__).parent.parent.parent
_DEFAULT_CONFIGS_DIR: Path = _REPO_ROOT / "configs"

_CONFIG_NAMES = (
    "asr",
    "decomposition",
    "retrieval",
    "nli_finetune",
    "scoring",
    "calibration",
)

# Canonical tag — printed and logged on every load for any unvalidated value.
PRE_CALIBRATION_TAG = "PRE-CALIBRATION DEFAULT — NOT VALIDATED"

# Human-readable labels for the four calibration hyperparameters.
_PRE_CAL_LABELS: dict[str, str] = {
    "tau":   "τ   (contradiction gate)",
    "tau_e": "τ_E (entailment-priority threshold)",
    "alpha": "α   (neutral weight)",
    "k":     "k   (BGE-M3 Top-k cap)",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Config:
    """
    Central config object for Interview IQ.

    Instantiating this class automatically:
      1. Loads all six YAML files from `configs/`.
      2. Prints the PRE-CALIBRATION tag and current hyperparameter values to
         stdout and emits a WARNING-level log entry.

    Parameters
    ----------
    configs_dir:
        Override the default `<repo_root>/configs/` directory — useful in tests.
    """

    def __init__(self, configs_dir: Path | str | None = None) -> None:
        self._configs_dir: Path = (
            Path(configs_dir) if configs_dir is not None else _DEFAULT_CONFIGS_DIR
        )
        self._raw: dict[str, dict[str, Any]] = {
            name: _load_yaml(self._configs_dir / f"{name}.yaml")
            for name in _CONFIG_NAMES
        }
        self._warn_pre_calibration()

    # ── sub-config properties (raw dicts) ─────────────────────────────────────

    @property
    def asr(self) -> dict[str, Any]:
        """Raw ASR config dict (configs/asr.yaml)."""
        return self._raw["asr"]

    @property
    def decomposition(self) -> dict[str, Any]:
        """Raw decomposition config dict (configs/decomposition.yaml)."""
        return self._raw["decomposition"]

    @property
    def retrieval(self) -> dict[str, Any]:
        """Raw retrieval config dict (configs/retrieval.yaml)."""
        return self._raw["retrieval"]

    @property
    def nli_finetune(self) -> dict[str, Any]:
        """Raw NLI fine-tuning config dict (configs/nli_finetune.yaml)."""
        return self._raw["nli_finetune"]

    @property
    def scoring(self) -> dict[str, Any]:
        """Raw scoring config dict (configs/scoring.yaml)."""
        return self._raw["scoring"]

    @property
    def calibration(self) -> dict[str, Any]:
        """Raw calibration config dict (configs/calibration.yaml)."""
        return self._raw["calibration"]

    # ── pre-calibration hyperparameter shortcuts ───────────────────────────────

    @property
    def tau(self) -> float:
        """τ — contradiction gate (PRE-CALIBRATION DEFAULT — NOT VALIDATED)."""
        return float(self._raw["scoring"]["thresholds"]["tau"])

    @property
    def tau_e(self) -> float:
        """τ_E — entailment-priority threshold (PRE-CALIBRATION DEFAULT — NOT VALIDATED)."""
        return float(self._raw["scoring"]["thresholds"]["tau_e"])

    @property
    def alpha(self) -> float:
        """α — neutral weight (PRE-CALIBRATION DEFAULT — NOT VALIDATED)."""
        return float(self._raw["scoring"]["thresholds"]["alpha"])

    @property
    def k(self) -> int:
        """k — BGE-M3 Top-k cap (PRE-CALIBRATION DEFAULT — NOT VALIDATED)."""
        return int(self._raw["retrieval"]["top_k"]["k"])

    # ── model name shortcuts ───────────────────────────────────────────────────

    @property
    def nli_model(self) -> str:
        """HuggingFace model ID for the NLI base model."""
        return str(self._raw["nli_finetune"]["model"]["base"])

    @property
    def embedding_model(self) -> str:
        """HuggingFace model ID for the BGE-M3 embedding model."""
        return str(self._raw["retrieval"]["model"]["name"])

    @property
    def asr_model(self) -> str:
        """Model checkpoint identifier for faster-whisper."""
        return str(self._raw["asr"]["model"]["checkpoint"])

    # ── internal helpers ───────────────────────────────────────────────────────

    def _warn_pre_calibration(self) -> None:
        """Print and log the pre-calibration tag for every unvalidated value."""
        values = {
            "tau":   self.tau,
            "tau_e": self.tau_e,
            "alpha": self.alpha,
            "k":     self.k,
        }
        lines = [f"[Config] {PRE_CALIBRATION_TAG}"]
        for key, label in _PRE_CAL_LABELS.items():
            lines.append(f"  {label} = {values[key]!r}")
        message = "\n".join(lines)
        print(message)
        logger.warning(message)

    def __repr__(self) -> str:
        return f"Config(configs_dir={self._configs_dir!r})"
