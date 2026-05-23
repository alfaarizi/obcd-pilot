# Training Guide

How to train the OBCD checkpoints the desktop app loads at runtime.

## Quickstart

```bash
pip install -e '.[training]'
python -m tools.train --variant all
```

Outputs land in `weights/`:

| File | Contents |
|---|---|
| `obcd_conv.pth`, `obcd_trans.pth` | Checkpoints picked by best validation F1. |
| `obcd_{variant}.report.json` | Per-epoch and test metrics. |

All files in `weights/` are gitignored.

## Dataset layout

Place Obcdset under `datasets/` at the project root. Override with `--data-root`.

```
datasets/
  add/        A/  B/  label/
  remove/     A/  B/  label/
  replacewithnew/
  gradually/
  light/
  aragement/
  shifting/
```

Labels are binary PNG masks. Any non-zero pixel marks a positive pair, all zeros marks negative.

## CLI reference

`python -m tools.train --help` prints the same table.

| Flag | Default | Description |
|---|---|---|
| `--variant {conv,trans,all}` | `conv` | Which model to train. `all` runs conv then trans. |
| `--data-root PATH` | `<repo>/datasets` | Obcdset scenario folders. |
| `--output-dir PATH` | `<repo>/weights` | Where checkpoints and reports go. |
| `--epochs INT` | `10` | Training epochs. |
| `--batch-size INT` | `4` | Batch size for all loaders. |
| `--learning-rate FLOAT` | `3e-3` | AdamW learning rate. |
| `--num-negatives INT` | `20` | Negatives sampled per source scenario. |
| `--num-workers INT` | `0` | DataLoader workers. Keep `0` on macOS / MPS. |
| `--seed INT` | `42` | RNG seed for Python, NumPy, and PyTorch. |
| `--train-ratio FLOAT` | `0.6` | Train split fraction. |
| `--val-ratio FLOAT` | `0.2` | Val split fraction (test is the remainder). |
| `--device {auto,cpu,cuda,mps}` | `auto` | Compute device. `auto` picks CUDA, then MPS, then CPU. |
| `--yolo-weights STR` | `yolov8n.pt` | YOLO weights file. |
| `--balance-classes` / `--no-balance-classes` | on | Sample positives and negatives equally per batch via `WeightedRandomSampler`. Disable for notebook-fidelity uniform sampling. |
| `-h, --help` | | Print help and exit. |

Defaults match the upstream OBCD notebooks. Per-variant scenarios are fixed. Conv uses `replacewithnew`, `add`, `remove`. Trans uses `gradually`, `light`. Both add negatives from `aragement` and `shifting`.

## Colab

`tools/train_colab.ipynb` runs the same CLI on a Colab GPU runtime.

1. Open the notebook in Colab and set the runtime to GPU.
2. Edit the second cell using the keys below.
3. Run all cells.

| Key | Meaning |
|---|---|
| `BRANCH` | Branch to clone (default `main`). |
| `DATASET_ROOT` | Drive path with the scenario folders. |
| `OUTPUT_ROOT` | Drive path to copy checkpoints into. |

## Caveats

Most Obcdset labels on disk are all-zero. For example, `add/` has 7 positives in 288 frames. The notebook selection rule keeps only the labelled transitions, so the effective training set is small.

ConvOBCD's `metadata_fc[1]` and `combined_fc[0]` are rebuilt every forward pass and their saved weights are stripped at load time. This is intentional and matches the research training behaviour.
