# ADR-005: Use QThread for pipeline execution

Date: 2026-05-08

## Status

Accepted

## Context

The OBCD pipeline (YOLOv8, MobileNetV2, TransOBCD/ConvOBCD) runs heavy ML inference. Running it on the main thread freezes the UI.

## Decision

Run the pipeline in a QThread. It emits Qt signals when it produces results, and the UI thread picks them up.

## Consequences

The UI stays responsive during inference because PyTorch and OpenCV release the GIL during their C++ computations. QThread with signals is PySide6's official pattern for this.

Rejected alternative: multiprocessing (adds IPC complexity and makes PyInstaller packaging harder).