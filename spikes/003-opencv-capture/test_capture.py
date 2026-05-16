"""Test webcam and video file capture via OpenCV.

Run with --source 0 for webcam, or --source path/to/file.mp4 for video.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class CaptureResult:
    source: int | str
    backend: str
    source_fps: float
    source_size: tuple[int, int]

    shape: tuple[int, ...]
    dtype: str
    has_bgr: bool

    frames_requested: int
    frames_captured: int
    measured_fps: float
    mean_read_ms: float


def capture_frames(source: int | str, count: int = 100):
    """Capture count frames from source and return diagnostics."""
    cap = cv2.VideoCapture(source)
    assert cap.isOpened(), f"cv2.VideoCapture({source!r}) failed to open"
    
    backend = cap.getBackendName()
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    source_size = (
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    )
    
    durations: list[float] = []
    expected_shape: tuple[int, ...] | None = None
    expected_dtype = ""
    has_bgr = False

    try:
        for _ in range(count):
            t0 = time.perf_counter()
            ok, frame = cap.read()
            durations.append(time.perf_counter() - t0)

            assert ok and frame is not None, "cap.read() returned an empty frame"
            
            if expected_shape is None:
                expected_shape, expected_dtype = frame.shape, str(frame.dtype)
                has_bgr = bool(np.array_equal(
                    frame,
                    cv2.cvtColor(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                        cv2.COLOR_RGB2BGR
                    ),
                ))
            
            assert frame.shape == expected_shape, f"shape changed: {expected_shape} to {frame.shape}"
    finally:
        cap.release()
    
    mean_duration = np.asarray(durations).mean()

    return CaptureResult(
        source=source,
        backend=backend,
        source_fps=source_fps,
        source_size=source_size,
        shape=expected_shape,
        dtype=expected_dtype,
        has_bgr=has_bgr,
        frames_requested=count,
        frames_captured=len(durations),
        measured_fps=1.0 / mean_duration,
        mean_read_ms=mean_duration * 1000.0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPIKE-003")
    parser.add_argument("--source", default="0")
    parser.add_argument("--frames", type=int, default=100)
    args = parser.parse_args()
    
    source: int | str = int(args.source) if args.source.isdigit() else args.source
    
    for field, value in asdict(capture_frames(source, args.frames)).items():
        print(f"{field}: {value}")