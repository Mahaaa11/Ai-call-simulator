#!/usr/bin/env python3
"""Launcher for avatar FastAPI server (run from web/ directory)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from avatar_server.main import main

if __name__ == "__main__":
    main()
