"""Acquires frames from webcam or video file."""

from obcd_pilot.capture._types import Camera, Frame
from obcd_pilot.capture.camera_worker import CameraWorker, retrieve_cameras

__all__ = [
    "Camera",
    "CameraWorker",
    "Frame",
    "retrieve_cameras",
]
