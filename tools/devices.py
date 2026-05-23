"""Device selection helpers shared by the training entry points."""

import logging

import torch

logger = logging.getLogger(__name__)


def autodetect() -> torch.device:
    """Pick CUDA, then MPS, then CPU. Logs the choice."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info("Training device: %s", device)
    return device
