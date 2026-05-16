"""Test if a PyInstaller-frozen executable starts without errors.

Run with path/to/frozen/executable as argument.
"""

import argparse
import platform
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path


STARTUP_WAIT_S = 5
TERMINATE_TIMEOUT_S = 5


@dataclass(slots=True)
class FreezeResult:
    """Diagnostics from launching a frozen executable."""
    exe: str
    os_arch: str
    is_started: bool
    exit_code: int | None
    stderr: str


def verify_frozen(exe: Path) -> FreezeResult:
    """Launch frozen binary and check whether it survives STARTUP_WAIT_S seconds."""
    assert exe.exists(), f"{exe} not found"

    os_arch = f"{platform.system()} {platform.machine()}"

    try:
        proc = subprocess.Popen(
            [str(exe)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(STARTUP_WAIT_S)

        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=TERMINATE_TIMEOUT_S)
            return FreezeResult(
                exe=str(exe),
                os_arch=os_arch,
                is_started=True,
                exit_code=None,
                stderr="",
            )

        stderr = proc.stderr.read().decode(errors="replace")[:500]
        return FreezeResult(
            exe=str(exe),
            os_arch=os_arch,
            is_started=proc.returncode == 0,
            exit_code=proc.returncode,
            stderr=stderr,
        )

    except Exception as exc:
        return FreezeResult(
            exe=str(exe),
            os_arch=os_arch,
            is_started=False,
            exit_code=None,
            stderr=str(exc),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPIKE-002")
    parser.add_argument("exe")
    args = parser.parse_args()

    result = verify_frozen(Path(args.exe))

    for field, value in asdict(result).items():
        print(f"{field}: {value}")

    assert result.is_started, f"frozen executable failed: {result.stderr}"