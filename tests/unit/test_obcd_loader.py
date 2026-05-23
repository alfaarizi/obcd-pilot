"""Unit tests for model loading and frame preprocessing."""

from pathlib import Path
from unittest.mock import patch

import pytest
import torch
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from obcd_pilot.pipeline._loader import load_model, qimage_to_tensor
from obcd_pilot.pipeline._types import ModelVariant

_LOADER = "obcd_pilot.pipeline._loader"


class TestQImageToTensor:
    """Tests for qimage_to_tensor."""

    @pytest.mark.parametrize("width,height", [(64, 48), (13, 7), (1280, 720)])
    def test_scales_to_fixed_input_shape(
        self, qapp: object, width: int, height: int
    ) -> None:
        """Stretches any input to (1, 3, 256, 256) float32 in [0, 1]."""
        image = QImage(width, height, QImage.Format.Format_RGB888)
        image.fill(Qt.GlobalColor.red)
        tensor = qimage_to_tensor(image)
        assert tensor.shape == (1, 3, 256, 256)
        assert tensor.dtype == torch.float32
        assert float(tensor.min()) >= 0.0
        assert float(tensor.max()) <= 1.0

    def test_channel_order_is_rgb(self, qapp: object) -> None:
        """A red fill maps to a high red channel and near-zero others."""
        image = QImage(64, 48, QImage.Format.Format_RGB888)
        image.fill(Qt.GlobalColor.red)
        tensor = qimage_to_tensor(image)
        assert float(tensor[0, 0].mean()) == pytest.approx(1.0, abs=1e-3)
        assert float(tensor[0, 1].mean()) == pytest.approx(0.0, abs=1e-3)
        assert float(tensor[0, 2].mean()) == pytest.approx(0.0, abs=1e-3)


class TestLoadModel:
    """Tests for load_model variant selection and checkpoint handling."""

    @pytest.mark.parametrize(
        "variant,evals_temporal_fc",
        [("conv", True), ("trans", False)],
    )
    def test_evals_subcomponents_without_yolo_landmine(
        self, qapp: object, variant: ModelVariant, evals_temporal_fc: bool
    ) -> None:
        """eval() must not be called on the composite (would trigger YOLO training)."""
        with (
            patch(f"{_LOADER}.YOLO"),
            patch(f"{_LOADER}.ConvOBCDModel") as conv_cls,
            patch(f"{_LOADER}.TransOBCDModel") as trans_cls,
        ):
            load_model(None, variant)
        model_cls = conv_cls if variant == "conv" else trans_cls
        model_cls.return_value.set_eval.assert_called_once()
        model_cls.return_value.eval.assert_not_called()
        if evals_temporal_fc:
            model_cls.return_value.temporal_fc.eval.assert_called_once()

    def test_skips_load_when_checkpoint_missing(
        self, qapp: object, tmp_path: Path
    ) -> None:
        """A checkpoint path that does not exist skips weight loading."""
        with (
            patch(f"{_LOADER}.YOLO"),
            patch(f"{_LOADER}.ConvOBCDModel") as conv_cls,
            patch(f"{_LOADER}.TransOBCDModel"),
        ):
            load_model(tmp_path / "absent.pth", "conv")
        conv_cls.return_value.load_state_dict.assert_not_called()

    def test_loads_conv_checkpoint_without_strict(
        self, qapp: object, tmp_path: Path
    ) -> None:
        """ConvOBCD weights load with strict=False to skip rebuilt layers."""
        checkpoint = tmp_path / "obcd_conv.pth"
        checkpoint.touch()
        state = {"model_state_dict": {"weight": 1}}
        with (
            patch(f"{_LOADER}.YOLO"),
            patch(f"{_LOADER}.ConvOBCDModel") as conv_cls,
            patch(f"{_LOADER}.TransOBCDModel"),
            patch(f"{_LOADER}.torch.load", return_value=state),
        ):
            load_model(checkpoint, "conv")
        conv_cls.return_value.load_state_dict.assert_called_once_with(
            {"weight": 1}, strict=False
        )

    def test_loads_trans_checkpoint_strict_with_max_objects(
        self, qapp: object, tmp_path: Path
    ) -> None:
        """TransOBCD reads max_objects and loads weights strictly."""
        checkpoint = tmp_path / "obcd_trans.pth"
        checkpoint.touch()
        state = {"model_state_dict": {"weight": 1}, "max_objects": 7}
        with (
            patch(f"{_LOADER}.YOLO"),
            patch(f"{_LOADER}.ConvOBCDModel"),
            patch(f"{_LOADER}.TransOBCDModel") as trans_cls,
            patch(f"{_LOADER}.torch.load", return_value=state),
        ):
            load_model(checkpoint, "trans")
        assert trans_cls.call_args.kwargs["max_objects"] == 7
        trans_cls.return_value.load_state_dict.assert_called_once_with(
            {"weight": 1}, strict=True
        )
