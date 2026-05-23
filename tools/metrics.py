"""Binary classification metrics computed without scikit-learn.

Mirrors the notebook's accuracy, precision, recall, and F1 reporting using
only PyTorch so the training script has no extra dependencies.
"""

from dataclasses import dataclass

import torch


@dataclass(frozen=True, slots=True)
class BinaryMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float


def _confusion(preds: torch.Tensor, labels: torch.Tensor) -> tuple[int, int, int, int]:
    """Return (tp, fp, fn, tn) for matching 0/1 tensors."""
    preds = preds.bool()
    labels = labels.bool()

    tp = int((preds & labels).sum().item())
    fp = int((preds & ~labels).sum().item())
    fn = int((~preds & labels).sum().item())
    tn = int((~preds & ~labels).sum().item())
    return tp, fp, fn, tn


def compute_metrics(preds: torch.Tensor, labels: torch.Tensor) -> BinaryMetrics:
    """Accuracy, precision, recall, and F1 from binarised predictions.

    Follows sklearn's zero_division=1 convention. When a denominator is zero
    the metric scores 1.0, so a model that was never asked to predict a
    positive (or a split with no positives) is not penalised.
    """
    tp, fp, fn, tn = _confusion(preds, labels)
    total = tp + fp + fn + tn

    accuracy = (tp + tn) / total if total else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return BinaryMetrics(accuracy=accuracy, precision=precision, recall=recall, f1=f1)
