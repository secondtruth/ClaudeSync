#!/usr/bin/env python
"""
ClaudeSync Simple GUI Launcher
Cross-platform launcher script
"""
import sys
import os
from pathlib import Path

# Add gui-simple directory to path
gui_path = Path(__file__).parent / "gui-simple"
sys.path.insert(0, str(gui_path))

# Import and run
try:
    from simple_gui import main
    main()
except ImportError as e:
    print(f"Error importing Simple GUI: {e}")
    print("\nPlease install required dependencies:")
    print("  pip install customtkinter")
    print("  pip install claudesync")
    sys.exit(1)
