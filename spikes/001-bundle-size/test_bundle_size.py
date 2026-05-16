"""Measure a PyInstaller dist directory and assert bundle stays under threshold.

Run after freezing with optional path/to/dist argument.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


SIZE_THRESHOLD_MB = 2048
BYTES_PER_MB = 1024 ** 2


class Component(NamedTuple):
    name: str
    size_mb: float
    percent_of_bundle: float


class File(NamedTuple):
    path: str
    size_mb: float


@dataclass(slots=True)
class BundleResult:
    size_mb: float
    is_oversized: bool
    largest_components: list[Component]
    largest_files: list[File]


def measure(dist_dir: Path) -> BundleResult:
    """Walk dist_dir and return size breakdown."""
    assert dist_dir.is_dir(), f"{dist_dir} does not exist."

    all_files = [(f, f.stat().st_size) for f in dist_dir.rglob("*") if f.is_file()]
    total_bytes = sum(size for _, size in all_files)

    component_bytes: dict[str, int] = {}
    for path, size in all_files:
        rel = path.relative_to(dist_dir)
        component = rel.parts[0] if len(rel.parts) > 1 else str(rel)
        component_bytes[component] = component_bytes.get(component, 0) + size

    return BundleResult(
        size_mb=total_bytes / BYTES_PER_MB,
        is_oversized=total_bytes > SIZE_THRESHOLD_MB * BYTES_PER_MB,
        largest_components=[
            Component(name, size_bytes / BYTES_PER_MB, size_bytes / total_bytes * 100)
            for name, size_bytes in sorted(
                component_bytes.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        ],
        largest_files=[
            File(str(path.relative_to(dist_dir)), size_bytes / BYTES_PER_MB)
            for path, size_bytes in sorted(
                all_files,
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPIKE-001")
    parser.add_argument("dist_dir", nargs="?", default="dist/obcd_spike")
    args = parser.parse_args()

    result = measure(Path(args.dist_dir))

    print(f"Bundle Size: {result.size_mb:.1f} MB")

    for name, size_mb, pct in result.largest_components:
        print(f"{name}: {size_mb:.1f} MB ({pct:.1f}%)")

    for path, size_mb in result.largest_files:
        print(f"{path}: {size_mb:.1f} MB")

    assert not result.is_oversized, (
        f"Bundle is {result.size_mb:.1f} MB, exceeds {SIZE_THRESHOLD_MB} MB"
    )