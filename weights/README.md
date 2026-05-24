# Weights

OBCD checkpoints. Files in this directory are gitignored.

In development, launch the desktop app from the repo root to load checkpoints from this folder.

For installed builds, copy the checkpoints into the per-user Qt `AppDataLocation`:

- macOS: `~/Library/Application Support/obcd-pilot/weights`
- Linux: `~/.local/share/obcd-pilot/weights`
- Windows: `%APPDATA%\obcd-pilot\weights`

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
