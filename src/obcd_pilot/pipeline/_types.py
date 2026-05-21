"""Data types for the OBCD pipeline."""

from dataclasses import dataclass
from typing import Literal

ModelVariant = Literal["conv", "trans"]


@dataclass(frozen=True, slots=True)
class Detection:
    """The result of comparing two consecutive frames.

    Attributes:
        frame_id: Monotonically increasing counter for the second frame.
        timestamp_ms: Wall-clock time of the detection in milliseconds.
        change_detected: ``True`` when ``confidence`` clears the threshold.
        confidence: Sigmoid output in ``[0.0, 1.0]``.
        inference_ms: End-to-end inference time in milliseconds.
        model_name: name of the model that produced the result.
    """

    frame_id: int
    timestamp_ms: float
    change_detected: bool
    confidence: float
    inference_ms: float
    model_name: Literal["ConvOBCD", "TransOBCD"]
