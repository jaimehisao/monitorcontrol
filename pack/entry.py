"""PyInstaller entry. Adds src/ when run unfrozen from a checkout."""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    src = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(src))

from monitorcontrol.cli import main

if __name__ == "__main__":
    main()
