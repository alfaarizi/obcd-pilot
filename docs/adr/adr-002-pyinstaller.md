# ADR-002: Use PyInstaller for packaging

Date: 2026-05-08

## Status

Accepted

## Context

Users must install and run the app without Python or any developer tools on their machine.

## Decision

Use PyInstaller to bundle the app into a platform-specific binary.

## Consequences

PyInstaller freezes the interpreter and all dependencies into one distributable. Each platform needs its own build. Build times are slower than running from source, and the bundle will be large because of PyTorch and OpenCV.