# Weights

OBCD checkpoints. Checkpoint artifacts are gitignored, but this README is tracked.

In development, launch the desktop app from the repo root to load checkpoints from this folder.

For installed builds, copy the checkpoints into the per-user Qt `AppDataLocation`:

- macOS: `~/Library/Application Support/OBCD/obcd-pilot/weights`
- Linux: `~/.local/share/OBCD/obcd-pilot/weights`
- Windows: `%APPDATA%\OBCD\obcd-pilot\weights`

Set `OBCD_WEIGHTS_DIR` to point at any other folder.

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
