"""Acquires frames from webcam or video file."""

from obcd_pilot.capture._types import CameraInfo, Frame, Playback
from obcd_pilot.capture.camera_worker import CameraWorker, retrieve_cameras
from obcd_pilot.capture.video_worker import VideoWorker

__all__ = [
    "CameraWorker",
    "VideoWorker",
    "Frame",
    "Playback",
    "CameraInfo",
    "retrieve_cameras",
]
