"""Runs detection and classification on frame pairs."""

from obcd_pilot.pipeline._types import Detection, ModelVariant
from obcd_pilot.pipeline.obcd_worker import OBCDWorker

__all__ = [
    "Detection",
    "ModelVariant",
    "OBCDWorker",
]
