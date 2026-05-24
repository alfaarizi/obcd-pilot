"""Model construction, checkpoint loading, and frame preprocessing."""

import logging
import os
from functools import cache
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
_YOLO_WEIGHTS = os.environ.get("OBCD_YOLO_WEIGHTS", "yolov8n.pt")


@cache
def autodetect() -> torch.device:
    """Pick CUDA, then MPS, then CPU. Cached after first call."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


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
    device = autodetect()
    if not Path(_YOLO_WEIGHTS).exists():
        logger.warning(
            "YOLO weights %r not found on disk; ultralytics may attempt a "
            "network download. Set OBCD_YOLO_WEIGHTS to a local path to avoid this.",
            _YOLO_WEIGHTS,
        )
    yolo = YOLO(_YOLO_WEIGHTS)
    # Move and freeze the inner nn.Module directly. yolo.eval() triggers training.
    yolo_inner = cast(torch.nn.Module, yolo.model)
    yolo_inner.to(device).eval()
    yolo_inner.requires_grad_(False)
    feature_extractor = torch.nn.Sequential()

    checkpoint: _Checkpoint | None = None
    if checkpoint_path is not None and checkpoint_path.exists():
        checkpoint = cast(
            _Checkpoint,
            torch.load(checkpoint_path, map_location=device, weights_only=True),
        )

    model: OBCDModel
    if variant == "conv":
        model = ConvOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=device,
        )
    else:
        max_objects = 10
        if checkpoint is not None:
            max_objects = checkpoint.get("max_objects", max_objects)
        model = TransOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=device,
            max_objects=max_objects,
        )

    if checkpoint is not None:
        # YOLO and feature_extractor are frozen and rebuilt from disk;
        # never load their weights from the OBCD checkpoint.
        state = {
            k: v
            for k, v in checkpoint["model_state_dict"].items()
            if not k.startswith(("yolo_model.", "feature_extractor."))
        }
        if variant == "conv":
            # metadata_fc.1 and combined_fc.0 are rebuilt each forward pass;
            # their saved shapes will not match the fresh model.
            state = {
                k: v
                for k, v in state.items()
                if not k.startswith(("metadata_fc.1.", "combined_fc.0."))
            }
            model.load_state_dict(state, strict=False)
        else:
            model.load_state_dict(state, strict=False)
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
    """Convert a QImage to a (1, 3, 256, 256) RGB float tensor in [0, 1].

    The image is stretched to 256x256 without preserving aspect ratio, matching
    the Resize((256, 256)) transform the models were trained with.
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
