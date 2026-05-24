"""Background worker that produces change detections from consecutive frames."""

import time
from pathlib import Path
from typing import Literal

import torch
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from obcd_pilot.capture import Frame
from obcd_pilot.pipeline import (
    Detection,
    ModelVariant,
    OBCDModel,
    load_model,
    qimage_to_tensor,
)

_CHANGE_THRESHOLD = 0.5

_MODEL_NAMES: dict[ModelVariant, Literal["ConvOBCD", "TransOBCD"]] = {
    "conv": "ConvOBCD",
    "trans": "TransOBCD",
}


class OBCDWorker(QObject):
    sig_detection = Signal(Detection)
    sig_model_ready = Signal(str)

    def __init__(
        self,
        variant: ModelVariant = "conv",
        checkpoint_path: Path | None = None,
        num_classes: int = 80,
    ) -> None:
        super().__init__()
        self._variant = variant
        self._checkpoint_path = checkpoint_path
        self._num_classes = num_classes

        self._model: OBCDModel | None = None
        self._prev_tensor: torch.Tensor | None = None
        self._pending_frame: Frame | None = None
        self._is_scheduled = False
        self._frame_id = 0

    @Slot()
    def start_model(self) -> None:
        """Load the model on the worker's thread and announce its state."""
        self._model = load_model(
            self._checkpoint_path, self._variant, self._num_classes
        )
        name = _MODEL_NAMES[self._variant]
        trained = self._checkpoint_path is not None and self._checkpoint_path.exists()
        self.sig_model_ready.emit(name if trained else f"{name} (untrained)")

    @Slot(Frame)
    def push_frame(self, frame: Frame) -> None:
        """Store the latest frame and post one processing event if none is queued."""
        self._pending_frame = frame
        if not self._is_scheduled:
            self._is_scheduled = True
            QTimer.singleShot(0, self._process_latest_frame)

    @Slot()
    def _process_latest_frame(self) -> None:
        """Run inference on the currently pending frame and clear the slot."""
        self._is_scheduled = False
        model, frame = self._model, self._pending_frame
        if model is None or frame is None:
            return
        self._pending_frame = None
        self._run_inference(model, frame)

    def _run_inference(self, model: OBCDModel, frame: Frame) -> None:
        """Compare the frame with the previous one and emit a detection."""
        curr_tensor = qimage_to_tensor(frame.image).to(model.device)

        if self._prev_tensor is not None:
            start = time.perf_counter()
            with torch.inference_mode():
                confidence = float(model(self._prev_tensor, curr_tensor).item())
            inference_ms = (time.perf_counter() - start) * 1000.0

            self.sig_detection.emit(
                Detection(
                    frame_id=self._frame_id,
                    timestamp_ms=time.time() * 1000.0,
                    change_detected=confidence > _CHANGE_THRESHOLD,
                    confidence=confidence,
                    inference_ms=inference_ms,
                    model_name=_MODEL_NAMES[self._variant],
                )
            )

        self._prev_tensor = curr_tensor
        self._frame_id += 1
