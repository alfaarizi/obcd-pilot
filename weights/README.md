# Weights

Runtime OBCD checkpoints. Files in this directory are gitignored.

The application reads:

| File | Loaded by |
|---|---|
| `obcd_conv.pth` | ConvOBCD variant |
| `obcd_trans.pth` | TransOBCD variant |

Train them with:

```bash
pip install -e '.[training]'
python -m tools.train --variant all
```

See `docs/training.md` for the full guide.
