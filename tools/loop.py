"""Training and evaluation loops for ConvOBCD and TransOBCD."""

import copy
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tqdm import tqdm

from obcd_pilot.pipeline import ConvOBCDModel, OBCDModel, TransOBCDModel
from tools.metrics import BinaryMetrics, compute_metrics

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EpochReport:
    epoch: int
    train_loss: float
    train_metrics: BinaryMetrics
    val_loss: float
    val_metrics: BinaryMetrics
    elapsed_s: float


def _to_device(
    batch: Mapping[str, torch.Tensor], device: torch.device
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    # non_blocking=True overlaps the host->device copy with the previous
    # batch's compute when pin_memory is on (no-op otherwise).
    return (
        batch["image1"].to(device, non_blocking=True),
        batch["image2"].to(device, non_blocking=True),
        batch["label"].to(device, non_blocking=True),
    )


def _run_epoch(
    model: OBCDModel,
    loader: DataLoader[dict[str, torch.Tensor]],
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
    desc: str,
) -> tuple[float, BinaryMetrics]:
    """Run one pass over loader. Pass optimizer=None for evaluation."""
    train_mode = optimizer is not None
    if train_mode:
        model.set_train()
        if isinstance(model, ConvOBCDModel):
            model.temporal_fc.train()
    else:
        model.set_eval()
        if isinstance(model, ConvOBCDModel):
            model.temporal_fc.eval()

    loss_sum = 0.0
    n_samples = 0
    all_preds: list[torch.Tensor] = []
    all_labels: list[torch.Tensor] = []
    bar = tqdm(loader, desc=desc, leave=False)

    with torch.set_grad_enabled(train_mode):
        for batch in bar:
            img1, img2, label = _to_device(batch, device)
            target = label.unsqueeze(1)

            if train_mode:
                assert optimizer is not None
                optimizer.zero_grad()

            preds, _ = model(img1, img2)
            loss = criterion(preds, target)

            if train_mode:
                loss.backward()
                assert optimizer is not None
                optimizer.step()

            # Cache loss.item() once, each call forces a GPU->CPU sync.
            loss_value = float(loss.item())
            # Weight by batch size so partial last batches do not skew the mean.
            batch_size = label.size(0)
            loss_sum += loss_value * batch_size
            n_samples += batch_size

            with torch.no_grad():
                hard_preds = (preds.detach() > 0.5).float().cpu().squeeze(1)
                all_preds.append(hard_preds)
                all_labels.append(label.detach().cpu())

            bar.set_postfix(loss=f"{loss_value:.4f}")

    preds_t = torch.cat(all_preds) if all_preds else torch.empty(0)
    labels_t = torch.cat(all_labels) if all_labels else torch.empty(0)
    metrics = compute_metrics(preds_t, labels_t)
    mean_loss = loss_sum / max(n_samples, 1)
    return mean_loss, metrics


def _save_conv(model: ConvOBCDModel, path: Path) -> None:
    """Write the ConvOBCD checkpoint in the notebook's documented schema."""
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "metadata_fc_state_dict": model.metadata_fc.state_dict(),
            "feature_fc_state_dict": model.feature_fc.state_dict(),
            "combined_fc_state_dict": model.combined_fc.state_dict(),
            "whole_metadata_fc_state_dict": model.whole_metadata_fc.state_dict(),
        },
        path,
    )


def _save_trans(model: TransOBCDModel, path: Path) -> None:
    """Write the TransOBCD checkpoint, including the runtime max_objects."""
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "feature_embed_state_dict": model.feature_embed.state_dict(),
            "metadata_embed_state_dict": model.metadata_embed.state_dict(),
            "whole_metadata_embed_state_dict": (
                model.whole_metadata_embed.state_dict()
            ),
            "matched_transformer_state_dict": (model.matched_transformer.state_dict()),
            "unmatched_transformer_state_dict": (
                model.unmatched_transformer.state_dict()
            ),
            "combined_fc_state_dict": model.combined_fc.state_dict(),
            "max_objects": int(model.max_objects),
        },
        path,
    )


def save_checkpoint(model: OBCDModel, path: Path) -> None:
    """Dispatch to the per-variant save format and log the destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(model, ConvOBCDModel):
        _save_conv(model, path)
        name = "conv"
    else:
        _save_trans(model, path)
        name = "trans"
    logger.info("Wrote %s checkpoint to %s", name, path)


def train(
    model: OBCDModel,
    train_loader: DataLoader[dict[str, torch.Tensor]],
    val_loader: DataLoader[dict[str, torch.Tensor]],
    device: torch.device,
    *,
    num_epochs: int,
    learning_rate: float,
    checkpoint_path: Path,
) -> list[EpochReport]:
    """Train model and write the best-by-val-F1 checkpoint to disk."""
    criterion: nn.Module = nn.BCELoss()
    trainable: Iterable[nn.Parameter] = (
        p for p in model.parameters() if p.requires_grad
    )
    optimizer = AdamW(trainable, lr=learning_rate)

    history: list[EpochReport] = []
    best_f1 = -1.0
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(1, num_epochs + 1):
        t0 = time.time()
        train_loss, train_m = _run_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            device,
            f"train[{epoch}/{num_epochs}]",
        )
        val_loss, val_m = _run_epoch(
            model, val_loader, criterion, None, device, f"val[{epoch}/{num_epochs}]"
        )
        elapsed = time.time() - t0

        logger.info(
            "epoch %d  train_loss=%.4f acc=%.3f f1=%.3f | "
            "val_loss=%.4f acc=%.3f prec=%.3f rec=%.3f f1=%.3f | %.1fs",
            epoch,
            train_loss,
            train_m.accuracy,
            train_m.f1,
            val_loss,
            val_m.accuracy,
            val_m.precision,
            val_m.recall,
            val_m.f1,
            elapsed,
        )

        history.append(
            EpochReport(
                epoch=epoch,
                train_loss=train_loss,
                train_metrics=train_m,
                val_loss=val_loss,
                val_metrics=val_m,
                elapsed_s=elapsed,
            )
        )

        if val_m.f1 > best_f1:
            best_f1 = val_m.f1
            best_state = copy.deepcopy(model.state_dict())
            save_checkpoint(model, checkpoint_path)

    if best_state is not None:
        model.load_state_dict(best_state, strict=False)
    return history


def evaluate(
    model: OBCDModel,
    loader: DataLoader[dict[str, torch.Tensor]],
    device: torch.device,
    desc: str = "test",
) -> tuple[float, BinaryMetrics]:
    """Score model on loader without updating weights."""
    criterion = nn.BCELoss()
    return _run_epoch(model, loader, criterion, None, device, desc)
