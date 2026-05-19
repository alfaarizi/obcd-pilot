"""Acquires frames from webcam or video file."""

from obcd_pilot.capture._types import CameraInfo, Frame, VideoInfo
from obcd_pilot.capture.camera_worker import CameraWorker, retrieve_cameras

__all__ = [
    "CameraInfo",
    "CameraWorker",
    "Frame",
    "VideoInfo",
    "retrieve_cameras",
]
