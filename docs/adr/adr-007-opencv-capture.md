# ADR-007: Use OpenCV for video capture

Date: 2026-05-13

## Status

Accepted

## Context

The capture module must acquire frames from webcams and video files on Windows, macOS, and Linux.

## Decision

Use OpenCV (cv2.VideoCapture) for all frame acquisition.

## Consequences

OpenCV handles both live cameras and video files through the same API. It releases the GIL during I/O, which keeps the UI responsive on a QThread [ADR-005](https://github.com/alfaarizi/obcd-pilot/blob/main/docs/adr/adr-005-qthread-pipeline.md).

Rejected alternatives: QCamera (ties capture to the UI framework), GStreamer (harder to bundle with PyInstaller), imageio (limited webcam support).