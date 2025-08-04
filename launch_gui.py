#!/usr/bin/env python
"""
Direct launcher for ClaudeSync GUI
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Import and launch
from claudesync.gui.main import launch

if __name__ == "__main__":
    launch()
