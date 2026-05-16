"""Test whether PyTorch releases the GIL during inference on a QThread.

Run with optional --inferences N and --tick-ms N
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass

import numpy as np
import torch
from torchvision.models import MobileNet_V2_Weights, mobilenet_v2
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication


LATENCY_THRESHOLD_MS = 100.0


@dataclass(slots=True)
class LatencyResult:
    model_name: str
    device: str

    inference_count: int
    mean_inference_ms: float

    latency_count: int
    max_latency_ms: float
    p95_latency_ms: float
    is_ui_responsive: bool


class InferenceWorker(QThread):
    """Run model inference count times."""
    def __init__(self, model: torch.nn.Module, batch: torch.Tensor, inference_count: int) -> None:
        super().__init__()
        self.inference_durations: list[float] = []
        self._model = model
        self._batch = batch
        self._inference_count = inference_count

    def run(self) -> None:
        for _ in range(self._inference_count):
            t0 = time.perf_counter()
            with torch.no_grad():
                self._model(self._batch)
            self.inference_durations.append(time.perf_counter() - t0)


def run_test(inference_count: int, tick_ms: int) -> LatencyResult:
    """Measure main-thread event-loop latency while inference runs on a QThread."""
    app = QApplication([])

    model = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    latencies: list[float] = []
    last_tick = [time.perf_counter()]

    def on_tick() -> None:
        now = time.perf_counter()
        latencies.append((now - last_tick[0]) * 1000.0)
        last_tick[0] = now
    
    timer = QTimer()
    timer.setInterval(tick_ms)
    timer.timeout.connect(on_tick)
    
    worker = InferenceWorker(
        model,
        torch.randn(1, 3, 224, 224, device=device),
        inference_count,
    )
    worker.finished.connect(timer.stop)
    worker.finished.connect(app.quit)

    timer.start()
    worker.start()
    app.exec()

    assert latencies, "timer never fired, test is invalid"
    max_latency = float(max(latencies))
    inference_ms = [d * 1000.0 for d in worker.inference_durations]

    return LatencyResult(
        model_name="MobileNetV2",
        device=device,
        inference_count=len(inference_ms),
        mean_inference_ms=float(np.asarray(inference_ms).mean()),
        latency_count=len(latencies),
        max_latency_ms=max_latency,
        p95_latency_ms=float(np.percentile(latencies, 95)),
        is_ui_responsive=max_latency < LATENCY_THRESHOLD_MS,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPIKE-004")
    parser.add_argument("--inferences", type=int, default=20)
    parser.add_argument("--tick-ms", type=int, default=50)
    args = parser.parse_args()

    for field, value in asdict(run_test(args.inferences, args.tick_ms)).items():
        print(f"{field}: {value}")