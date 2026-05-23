"""Runs detection and classification on frame pairs."""

from obcd_pilot.pipeline._loader import OBCDModel, load_model, qimage_to_tensor
from obcd_pilot.pipeline._obcd import ConvOBCDModel, TransOBCDModel
from obcd_pilot.pipeline._types import Detection, ModelVariant
from obcd_pilot.pipeline.obcd_worker import OBCDWorker

__all__ = [
    "ConvOBCDModel",
    "Detection",
    "ModelVariant",
    "OBCDModel",
    "OBCDWorker",
    "TransOBCDModel",
    "load_model",
    "qimage_to_tensor",
]
