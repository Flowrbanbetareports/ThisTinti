#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    script = Path(__file__).with_suffix(".sh").resolve()
    os.execve("/bin/bash", ["bash", str(script)], os.environ.copy())  # nosec B606


if __name__ == "__main__":
    main()
