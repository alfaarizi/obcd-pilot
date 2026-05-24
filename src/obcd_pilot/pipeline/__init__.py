"""Runs detection and classification on frame pairs.

Heavy submodules (torch, ultralytics) load on first attribute access so
UI imports stay fast.
"""

import importlib
from typing import TYPE_CHECKING, Any

from obcd_pilot.pipeline._types import Detection, ModelVariant

if TYPE_CHECKING:
    from obcd_pilot.pipeline._loader import (
        OBCDModel,
        autodetect,
        load_model,
        qimage_to_tensor,
    )
    from obcd_pilot.pipeline._obcd import ConvOBCDModel, TransOBCDModel
    from obcd_pilot.pipeline.obcd_worker import OBCDWorker

__all__ = [
    "ConvOBCDModel",
    "Detection",
    "ModelVariant",
    "OBCDModel",
    "OBCDWorker",
    "TransOBCDModel",
    "autodetect",
    "load_model",
    "qimage_to_tensor",
]

_LAZY: dict[str, str] = {
    "ConvOBCDModel": "obcd_pilot.pipeline._obcd",
    "TransOBCDModel": "obcd_pilot.pipeline._obcd",
    "OBCDModel": "obcd_pilot.pipeline._loader",
    "OBCDWorker": "obcd_pilot.pipeline.obcd_worker",
    "autodetect": "obcd_pilot.pipeline._loader",
    "load_model": "obcd_pilot.pipeline._loader",
    "qimage_to_tensor": "obcd_pilot.pipeline._loader",
}


def __getattr__(name: str) -> Any:
    """PEP 562 lazy loader for heavy submodules."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
