"""Unit tests for OBCDWorker frame handling and inference."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot

from obcd_pilot.capture import Frame
from obcd_pilot.pipeline import Detection, ModelVariant
from obcd_pilot.pipeline.obcd_worker import OBCDWorker

_LOAD_MODEL = "obcd_pilot.pipeline.obcd_worker.load_model"


def _frame() -> Frame:
    """Return a small solid-colour frame for inference tests."""
    image = QImage(16, 12, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.red)
    return Frame(image, 16, 12, 30.0)


@pytest.fixture()
def worker(qapp: object) -> OBCDWorker:
    """An untrained ConvOBCD worker with no checkpoint."""
    return OBCDWorker(variant="conv", checkpoint_path=None)


class TestStartModel:
    """Tests for OBCDWorker.start_model."""

    @pytest.mark.parametrize(
        "variant,has_checkpoint,expected_name",
        [
            ("conv", False, "ConvOBCD (untrained)"),
            ("conv", True, "ConvOBCD"),
            ("trans", False, "TransOBCD (untrained)"),
        ],
    )
    def test_emits_display_name_with_trained_marker(
        self,
        qapp: object,
        tmp_path: Path,
        variant: ModelVariant,
        has_checkpoint: bool,
        expected_name: str,
    ) -> None:
        """start_model loads the model and announces its display name."""
        checkpoint: Path | None = None
        if has_checkpoint:
            checkpoint = tmp_path / "obcd.pth"
            checkpoint.touch()
        worker = OBCDWorker(variant=variant, checkpoint_path=checkpoint)
        received: list[str] = []
        worker.sig_model_ready.connect(received.append)
        with patch(_LOAD_MODEL, return_value=MagicMock()):
            worker.start_model()
        assert worker._model is not None
        assert received == [expected_name]


class TestPushFrame:
    """Tests for OBCDWorker.push_frame and inference scheduling."""

    def test_ignores_frame_until_model_loaded(
        self, worker: OBCDWorker, qtbot: QtBot
    ) -> None:
        """push_frame is a no-op while _model is None."""
        received: list[Detection] = []
        worker.sig_detection.connect(received.append)
        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: not worker._is_scheduled, timeout=1000)
        assert received == []
        assert worker._prev_tensor is None

    def test_emits_detection_on_second_frame(
        self, worker: OBCDWorker, qtbot: QtBot
    ) -> None:
        """The first frame primes the previous tensor. The second emits."""
        worker._model = MagicMock(return_value=torch.tensor([[0.8]]))
        received: list[Detection] = []
        worker.sig_detection.connect(received.append)

        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: worker._prev_tensor is not None, timeout=1000)
        assert received == []

        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: len(received) == 1, timeout=1000)

        detection = received[0]
        assert detection.frame_id == 1
        assert detection.confidence == pytest.approx(0.8)
        assert detection.model_name == "ConvOBCD"
        assert detection.inference_ms >= 0.0
        assert detection.timestamp_ms > 0.0

    @pytest.mark.parametrize(
        "confidence,expected_change",
        [
            (0.8, True),  # strictly above 0.5
            (0.5, False),  # exactly at 0.5
            (0.2, False),  # below 0.5
        ],
    )
    def test_change_flag_is_exclusive_at_threshold(
        self,
        worker: OBCDWorker,
        qtbot: QtBot,
        confidence: float,
        expected_change: bool,
    ) -> None:
        """change_detected is True only when confidence > 0.5."""
        worker._model = MagicMock(return_value=torch.tensor([[confidence]]))
        received: list[Detection] = []
        worker.sig_detection.connect(received.append)

        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: worker._prev_tensor is not None, timeout=1000)
        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: len(received) == 1, timeout=1000)

        assert received[0].change_detected is expected_change

    def test_coalesces_frames_arriving_during_inference(
        self, worker: OBCDWorker, qtbot: QtBot
    ) -> None:
        """A frame pushed mid-inference is processed once the worker is free."""
        calls: list[int] = []

        def infer(prev: torch.Tensor, curr: torch.Tensor) -> torch.Tensor:
            calls.append(1)
            if len(calls) == 1:
                worker.push_frame(_frame())
            return torch.tensor([[0.9]])

        worker._model = MagicMock(side_effect=infer)
        received: list[Detection] = []
        worker.sig_detection.connect(received.append)

        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: worker._prev_tensor is not None, timeout=1000)

        worker.push_frame(_frame())
        qtbot.waitUntil(lambda: len(received) == 2, timeout=1000)

        assert len(calls) == 2
        assert [d.frame_id for d in received] == [1, 2]
