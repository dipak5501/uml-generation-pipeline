#!/usr/bin/env python3
"""Print compute backend: apple-mlx, nvidia-cuda, or cpu."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def main() -> int:
    machine = platform.machine().lower()
    system = platform.system().lower()
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        print("apple-mlx")
        return 0
    nvidia = shutil.which("nvidia-smi")
    if nvidia:
        probe = subprocess.run([nvidia], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if probe.returncode == 0:
            print("nvidia-cuda")
            return 0
    try:
        import torch

        if torch.cuda.is_available():
            print("nvidia-cuda")
            return 0
    except ImportError:
        pass
    print("cpu")
    return 1


if __name__ == "__main__":
    sys.exit(main())
