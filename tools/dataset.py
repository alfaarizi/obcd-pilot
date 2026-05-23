"""Obcdset frame-pair dataset.

Layout: <root>/<scenario>/{A,B,label}/<id>.{jpg,jpg,png}. A is the "before"
image, B is "after", label is a binary PNG mask (any non-zero pixel = change).

Exposes a torch Dataset of (image1, image2, label) triples plus a
deterministic train/val/test splitter that mirrors the notebook's selection
rule: every positive pair, capped negatives per scenario.
"""

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import torch
from PIL import Image
from torch.utils.data import Dataset

_A_EXT = ".jpg"
_B_EXT = ".jpg"
_LABEL_EXT = ".png"


@dataclass(frozen=True, slots=True)
class Pair:
    """A single labelled frame pair."""

    scenario: str
    stem: str
    image_a: Path
    image_b: Path
    label: Path
    is_positive: bool


def _read_label_is_positive(path: Path) -> bool:
    """Return True when the mask contains any non-zero pixel.

    getbbox() runs in C and returns None when every pixel is zero, so we
    avoid allocating a NumPy array per file.
    """
    with Image.open(path) as img:
        return img.convert("L").getbbox() is not None


def _scenario_pairs(root: Path, scenario: str) -> list[Pair]:
    """Return every matched pair for a single scenario folder."""
    base = root / scenario
    a_dir, b_dir, label_dir = base / "A", base / "B", base / "label"
    if not (a_dir.is_dir() and b_dir.is_dir() and label_dir.is_dir()):
        raise FileNotFoundError(
            f"Scenario {scenario!r} is missing A/B/label under {base}"
        )

    a_stems = {p.stem for p in a_dir.glob(f"*{_A_EXT}")}
    b_stems = {p.stem for p in b_dir.glob(f"*{_B_EXT}")}
    label_stems = {p.stem for p in label_dir.glob(f"*{_LABEL_EXT}")}
    common = sorted(a_stems & b_stems & label_stems)

    pairs: list[Pair] = []
    for stem in common:
        label = label_dir / f"{stem}{_LABEL_EXT}"
        pairs.append(
            Pair(
                scenario=scenario,
                stem=stem,
                image_a=a_dir / f"{stem}{_A_EXT}",
                image_b=b_dir / f"{stem}{_B_EXT}",
                label=label,
                is_positive=_read_label_is_positive(label),
            )
        )
    return pairs


def collect_pairs(
    root: Path,
    scenarios: Sequence[str],
    num_negatives_per_scenario: int | None,
    seed: int,
) -> list[Pair]:
    """Collect every positive pair plus a capped number of negatives.

    Pass None for num_negatives_per_scenario to include all negatives, or 0
    to keep only positives.
    """
    rng = random.Random(seed)
    out: list[Pair] = []
    for scenario in scenarios:
        scenario_pairs = _scenario_pairs(root, scenario)
        positives = [p for p in scenario_pairs if p.is_positive]
        negatives = [p for p in scenario_pairs if not p.is_positive]
        out.extend(positives)
        if num_negatives_per_scenario is None:
            out.extend(negatives)
        elif num_negatives_per_scenario > 0:
            keep = min(num_negatives_per_scenario, len(negatives))
            out.extend(rng.sample(negatives, keep))
    return out


@dataclass(frozen=True, slots=True)
class Split:
    train: list[Pair]
    val: list[Pair]
    test: list[Pair]


def split_pairs(
    pairs: Sequence[Pair],
    train_ratio: float,
    val_ratio: float,
    seed: int,
) -> Split:
    """Shuffle and split pairs into train/val/test using the notebook's ratios."""
    if not (0.0 < train_ratio < 1.0 and 0.0 < val_ratio < 1.0):
        raise ValueError("Train/val ratios must be in (0, 1).")
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("Train + val ratios must leave room for the test split.")

    items = list(pairs)
    random.Random(seed).shuffle(items)
    n = len(items)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    return Split(
        train=items[:n_train],
        val=items[n_train : n_train + n_val],
        test=items[n_train + n_val :],
    )


class PairDataset(Dataset[dict[str, torch.Tensor]]):
    """Yields the dict shape the notebook training loop expects."""

    def __init__(
        self,
        pairs: Sequence[Pair],
        transform: Callable[[Image.Image], torch.Tensor],
    ) -> None:
        self._pairs = list(pairs)
        self._transform = transform

    def __len__(self) -> int:
        return len(self._pairs)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        pair = self._pairs[index]
        img_a = Image.open(pair.image_a).convert("RGB")
        img_b = Image.open(pair.image_b).convert("RGB")
        return {
            "image1": self._transform(img_a),
            "image2": self._transform(img_b),
            "label": torch.tensor(1.0 if pair.is_positive else 0.0),
        }


def summarize(pairs: Sequence[Pair]) -> str:
    """Return a one-line summary suitable for logging."""
    pos = sum(1 for p in pairs if p.is_positive)
    return f"{len(pairs)} pairs ({pos} positive, {len(pairs) - pos} negative)"
