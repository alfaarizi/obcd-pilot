"""Train ConvOBCD and/or TransOBCD on Obcdset and write a .pth checkpoint.

Usage:
    python -m tools.train --variant conv
    python -m tools.train --variant trans --epochs 10
    python -m tools.train --variant all --data-root datasets

Model classes are imported from obcd_pilot.pipeline so training and
inference share one architecture. Checkpoints land at
weights/obcd_{variant}.pth, which is where the runtime worker looks.
"""

import argparse
import json
import logging
import random
from dataclasses import asdict
from pathlib import Path
from typing import cast, get_args

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms

# Import YOLO from the submodule, as top-level import fails mypy strict mode.
from ultralytics.models import YOLO

from obcd_pilot.pipeline import (
    ConvOBCDModel,
    ModelVariant,
    OBCDModel,
    TransOBCDModel,
)
from tools import dataset as ds
from tools.devices import autodetect
from tools.loop import EpochReport, evaluate, train
from tools.metrics import BinaryMetrics

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VALID_VARIANTS: tuple[str, ...] = (*get_args(ModelVariant), "all")
_SCENARIOS: dict[str, tuple[str, ...]] = {
    "conv": ("replacewithnew", "add", "remove"),
    "trans": ("gradually", "light"),
}
_NEGATIVE_SOURCES: tuple[str, ...] = ("aragement", "shifting")
_DEFAULT_WEIGHTS_DIR = _PROJECT_ROOT / "weights"
_DEFAULT_DATA_ROOT = _PROJECT_ROOT / "datasets"

logger = logging.getLogger("obcd.train")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m tools.train",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--variant",
        choices=_VALID_VARIANTS,
        default="conv",
        help="Model to train. 'all' trains conv then trans sequentially.",
    )
    p.add_argument(
        "--data-root",
        type=Path,
        default=_DEFAULT_DATA_ROOT,
        help="Directory containing the Obcdset scenario folders (A/, B/, label/).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_WEIGHTS_DIR,
        help="Where to write obcd_{variant}.pth and obcd_{variant}.report.json.",
    )
    p.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs. Notebook default is 10.",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Batch size for all loaders. Notebook default is 4.",
    )
    p.add_argument(
        "--learning-rate",
        type=float,
        default=3e-3,
        help="AdamW learning rate. Notebook default is 0.003.",
    )
    p.add_argument(
        "--num-negatives",
        type=int,
        default=20,
        help="Negative pairs sampled per source scenario. Notebook uses 20.",
    )
    p.add_argument(
        "--num-workers",
        type=int,
        default=0,
        help="DataLoader worker processes. Keep 0 on macOS/MPS.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for Python, NumPy, and PyTorch RNGs.",
    )
    p.add_argument(
        "--train-ratio",
        type=float,
        default=0.6,
        help="Train split fraction. Notebook uses 0.6.",
    )
    p.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Validation split fraction. Test gets the remainder.",
    )
    p.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps"),
        default="auto",
        help="Compute device. 'auto' picks CUDA, then MPS, then CPU.",
    )
    p.add_argument(
        "--yolo-weights",
        type=str,
        default="yolov8n.pt",
        help="YOLO weights file. Notebook used yolov8n.pt.",
    )
    return p.parse_args()


def _seed_all(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch so dataset splits and inits reproduce."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _select_device(choice: str) -> torch.device:
    return autodetect() if choice == "auto" else torch.device(choice)


def _build_dataloaders(
    args: argparse.Namespace,
    variant: ModelVariant,
    device: torch.device,
) -> tuple[
    DataLoader[dict[str, torch.Tensor]],
    DataLoader[dict[str, torch.Tensor]],
    DataLoader[dict[str, torch.Tensor]],
]:
    """Build train/val/test loaders for one variant."""
    scenarios = _SCENARIOS[variant] + _NEGATIVE_SOURCES
    pairs = ds.collect_pairs(
        root=args.data_root,
        scenarios=scenarios,
        num_negatives_per_scenario=args.num_negatives,
        seed=args.seed,
    )
    logger.info("%s scenarios=%s -> %s", variant, scenarios, ds.summarize(pairs))

    split = ds.split_pairs(
        pairs,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )
    logger.info(
        "split: train=%s val=%s test=%s",
        ds.summarize(split.train),
        ds.summarize(split.val),
        ds.summarize(split.test),
    )

    train_tx = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(
                brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1
            ),
            transforms.ToTensor(),
        ]
    )
    test_tx = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
        ]
    )

    pin = device.type == "cuda"
    common = {
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "pin_memory": pin,
    }
    # drop_last on train avoids ragged BN batches. Val/test keep all samples
    # so reported metrics reflect the full split.
    return (
        DataLoader(
            ds.PairDataset(split.train, train_tx),
            shuffle=True,
            drop_last=True,
            **common,
        ),
        DataLoader(
            ds.PairDataset(split.val, test_tx),
            shuffle=False,
            drop_last=False,
            **common,
        ),
        DataLoader(
            ds.PairDataset(split.test, test_tx),
            shuffle=False,
            drop_last=False,
            **common,
        ),
    )


def _build_yolo(weights: str, device: torch.device) -> YOLO:
    """Instantiate YOLO and pin its inner nn.Module to device, frozen."""
    yolo = YOLO(weights)
    # ultralytics types yolo.model as str | None, but it is an nn.Module
    # once weights have loaded.
    inner = cast(nn.Module, yolo.model)
    inner.to(device)
    for param in inner.parameters():
        param.requires_grad = False
    inner.eval()
    return yolo


def _build_model(variant: ModelVariant, device: torch.device, yolo: YOLO) -> OBCDModel:
    """Construct an OBCD model with the notebook's empty feature_extractor."""
    feature_extractor = nn.Sequential()
    inner = cast(nn.Module, yolo.model)
    # ultralytics' inner model carries names as dict[int, str] mapping class
    # indices to labels. Fall back to the COCO default of 80 if absent.
    names: dict[int, str] | None = getattr(inner, "names", None)
    num_classes = len(names) if names else 80

    model: OBCDModel
    if variant == "conv":
        model = ConvOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=device,
        )
    else:
        model = TransOBCDModel(
            feature_extractor=feature_extractor,
            yolo_model=yolo,
            num_classes=num_classes,
            device=device,
        )
    model.to(device)
    return model


def _train_one(args: argparse.Namespace, variant: ModelVariant) -> None:
    """Train one variant end-to-end and write checkpoint + report."""
    _seed_all(args.seed)
    device = _select_device(args.device)
    train_loader, val_loader, test_loader = _build_dataloaders(args, variant, device)
    yolo = _build_yolo(args.yolo_weights, device)
    model = _build_model(variant, device, yolo)

    checkpoint_path = args.output_dir / f"obcd_{variant}.pth"
    history = train(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        num_epochs=args.epochs,
        learning_rate=args.learning_rate,
        checkpoint_path=checkpoint_path,
    )

    test_loss, test_metrics = evaluate(
        model, test_loader, device, desc=f"test[{variant}]"
    )
    logger.info(
        "test %s loss=%.4f acc=%.3f prec=%.3f rec=%.3f f1=%.3f",
        variant,
        test_loss,
        test_metrics.accuracy,
        test_metrics.precision,
        test_metrics.recall,
        test_metrics.f1,
    )

    report_path = args.output_dir / f"obcd_{variant}.report.json"
    _write_report(report_path, history, test_loss, test_metrics)


def _write_report(
    path: Path,
    history: list[EpochReport],
    test_loss: float,
    test_metrics: BinaryMetrics,
) -> None:
    """Persist per-epoch and test metrics next to the checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "epochs": [
            {
                "epoch": h.epoch,
                "train_loss": h.train_loss,
                "train_metrics": asdict(h.train_metrics),
                "val_loss": h.val_loss,
                "val_metrics": asdict(h.val_metrics),
                "elapsed_s": h.elapsed_s,
            }
            for h in history
        ],
        "test_loss": test_loss,
        "test_metrics": asdict(test_metrics),
    }
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote training report to %s", path)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    variants: tuple[ModelVariant, ...] = (
        ("conv", "trans") if args.variant == "all" else (args.variant,)
    )
    for variant in variants:
        logger.info("=== Training %s ===", variant)
        _train_one(args, variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
