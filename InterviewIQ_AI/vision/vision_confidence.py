"""Backward-compatible access to the canonical visual confidence analysis.

The rejected face-visibility/camera-engagement/head-stability formula was
removed. New code should import :mod:`visual_behavioral_confidence` directly.
"""
from __future__ import annotations

from typing import Any

try:
    from .visual_behavioral_confidence import (
        VisualConfidenceConfig,
        analyze_visual_behavioral_confidence,
        calculate_visual_confidence_summary,
    )
except ImportError:
    from visual_behavioral_confidence import (  # type: ignore
        VisualConfidenceConfig,
        analyze_visual_behavioral_confidence,
        calculate_visual_confidence_summary,
    )


def calculate_vision_confidence(
    windows: Any,
    config: VisualConfidenceConfig | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper accepting temporal probability windows."""
    return calculate_visual_confidence_summary(
        windows, config=config or VisualConfidenceConfig()
    )


__all__ = [
    "VisualConfidenceConfig",
    "analyze_visual_behavioral_confidence",
    "calculate_vision_confidence",
]
