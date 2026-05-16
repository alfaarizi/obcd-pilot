"""Minimal app stub for PyInstaller freeze testing.

Imports all heavy dependencies to verify they bundle and load correctly.
"""

import sys

import numpy as np
import cv2
import PySide6.QtCore
import PySide6.QtWidgets
import yaml
import torch
import torchvision
import ultralytics


if __name__ == "__main__":
    for name, version in {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "pyside6.QtCore": PySide6.QtCore.__version__,
        "pyside6.QtWidgets": PySide6.QtWidgets.__version__,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "ultralytics": ultralytics.__version__,
        "pyyaml": yaml.__version__,
    }.items():
        print(f"{name}: {version}")