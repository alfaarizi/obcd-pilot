"""Model construction, checkpoint loading, and frame preprocessing."""

import logging
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import numpy as np
import torch
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

# Import YOLO from the submodule, as top-level import fails mypy strict mode.
from ultralytics.models import YOLO

from obcd_pilot.pipeline._obcd import ConvOBCDModel, TransOBCDModel
from obcd_pilot.pipeline._types import ModelVariant

logger = logging.getLogger(__name__)

_INPUT_SIZE = 256
_DEVICE = torch.device("cpu")
_YOLO_WEIGHTS = "yolov8n.pt"

OBCDModel = ConvOBCDModel | TransOBCDModel


class _Checkpoint(TypedDict):
    """The checkpoint fields that load_model reads."""

    model_state_dict: dict[str, torch.Tensor]
    max_objects: NotRequired[int]


def load_model(
    checkpoint_path: Path | None,
    variant: ModelVariant,
    num_classes: int = 80,
) -> OBCDModel:
    """Build an OBCD model and load weights when a checkpoint is available."""
    yolo = YOLO(_YOLO_WEIGHTS)
    feature_extractor = torch.nn.Sequential()

    checkpoint: _Checkpoint | None = None
    if checkpoint_path is not None and checkpoint_path.exists():
        checkpoint = cast(
            _Checkpoint,
            torch.load(checkpoint_path, map_location=_DEVICE, weights_only=True),
        )

    model: OBCDModel
    if variant == "conv":
        model = ConvOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=_DEVICE,
        )
    else:
        max_objects = 10
        if checkpoint is not None:
            max_objects = checkpoint.get("max_objects", max_objects)
        model = TransOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=_DEVICE,
            max_objects=max_objects,
        )

    if checkpoint is not None:
        # ConvOBCD rebuilds layers each forward pass, so its checkpoint shapes
        # no longer match the fresh model. Load conv loosely, trans strictly.
        strict = variant == "trans"
        model.load_state_dict(checkpoint["model_state_dict"], strict=strict)
        logger.info("Loaded %s weights from %s", variant, checkpoint_path)
    else:
        logger.warning(
            "No checkpoint for %s, running with untrained weights. "
            "Confidence scores are not meaningful until a .pth is provided.",
            variant,
        )

    # ultralytics overrides .eval() on its YOLO submodule to launch dataset
    # training, so evaluating the whole model would start a training run. Switch
    # only the OBCD submodules to eval mode. Since set_eval() misses ConvOBCD's
    # temporal_fc dropout, disable that layer directly.
    model.set_eval()
    if variant == "conv":
        cast(ConvOBCDModel, model).temporal_fc.eval()
    return model


def qimage_to_tensor(image: QImage) -> torch.Tensor:
    """Convert a ``QImage`` to a ``(1, 3, 256, 256)`` RGB float tensor in ``[0, 1]``.

    The image is stretched to 256x256 without preserving aspect ratio, matching
    the ``Resize((256, 256))`` transform the models were trained with.
    """
    scaled = image.convertToFormat(QImage.Format.Format_RGB888).scaled(
        _INPUT_SIZE,
        _INPUT_SIZE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    width, height = scaled.width(), scaled.height()
    buffer = scaled.constBits()
    array = np.frombuffer(buffer, dtype=np.uint8, count=height * width * 3)
    array = array.reshape(height, width, 3)
    tensor = torch.from_numpy(array.copy()).permute(2, 0, 1).float().div(255.0)
    return tensor.unsqueeze(0)
