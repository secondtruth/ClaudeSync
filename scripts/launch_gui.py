#!/usr/bin/env python
"""Utilities to launch the ClaudeSync GUI without duplicating shell logic."""
from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
from typing import Callable, Sequence

from scripts._paths import ensure_simple_gui_on_path, ensure_src_on_path

ensure_src_on_path()

REQUIRED_MODULES = {
    "customtkinter": "customtkinter",
    "PIL": "pillow",
}


def module_available(import_name: str) -> bool:
    """Return True if *import_name* can be imported."""
    try:
        importlib.import_module(import_name)
    except ImportError:
        return False
    return True


def install_packages(packages: Sequence[str], verbose: bool = False) -> None:
    """Install missing packages using pip."""
    if not packages:
        return
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    if verbose:
        print("[info] Running:", " ".join(cmd))
    subprocess.check_call(cmd)


def ensure_gui_dependencies(install_missing: bool = True, verbose: bool = False) -> None:
    """Ensure GUI dependencies are importable, installing when needed."""
    missing = []
    for import_name, package_name in REQUIRED_MODULES.items():
        if not module_available(import_name):
            missing.append(package_name)
            if verbose:
                print(f"[warn] Missing Python module: {import_name}")
    if missing and install_missing:
        install_packages(sorted(set(missing)), verbose=verbose)
        for import_name in REQUIRED_MODULES:
            if not module_available(import_name):
                raise RuntimeError(f"Module {import_name} still missing after installation")
    elif missing:
        raise RuntimeError(
            "Missing GUI dependencies: " + ", ".join(sorted(set(missing)))
        )


def prefer_cli_launch() -> bool:
    """Return True if the csync CLI is available."""
    return shutil.which("csync") is not None


def import_gui_launcher() -> Callable[[], None]:
    """Import and return the GUI launch callable."""
    from claudesync.gui.main import launch

    return launch


def launch_full_gui(use_cli: bool = True, verbose: bool = False, debug: bool = False) -> int:
    """Launch the full ClaudeSync GUI and return an exit code."""
    if use_cli and prefer_cli_launch():
        result = subprocess.run(["csync", "gui", "launch"], check=False)
        if result.returncode == 0:
            return 0
        if verbose:
            print(f"[warn] csync gui launch exited with {result.returncode}; falling back.")
    if verbose and use_cli and not prefer_cli_launch():
        print("[info] csync CLI not found; importing GUI module directly.")
    try:
        gui_launch = import_gui_launcher()
        gui_launch()
    except Exception as exc:  # pragma: no cover
        if debug:
            raise
        print(f"Error launching ClaudeSync GUI: {exc}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        return 1
    return 0


def launch_simple_gui(verbose: bool = False, debug: bool = False) -> int:
    """Launch the lightweight simple GUI."""
    gui_path = ensure_simple_gui_on_path()
    try:
        from simple_gui import main as simple_main
    except ImportError as exc:
        print(f"Error importing Simple GUI: {exc}")
        print("\nEnsure the required dependencies are installed:")
        print("  pip install customtkinter")
        print("  pip install claudesync")
        print(f"  Add {gui_path} to PYTHONPATH if running outside the repo")
        return 1

    if verbose:
        print("[info] Launching simple GUI entry point.")
    try:
        simple_main()
    except Exception as exc:  # pragma: no cover
        if debug:
            raise
        print(f"Error running simple GUI: {exc}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc()
        return 1
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=("full", "simple"),
        default="full",
        help="Choose between the full GUI or the lightweight simple GUI.",
    )
    parser.add_argument(
        "--deps-only",
        action="store_true",
        help="Only ensure dependencies, do not launch the GUI.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Fail instead of installing missing dependencies.",
    )
    parser.add_argument(
        "--no-cli",
        action="store_true",
        help="Skip attempting to launch via the csync CLI (full GUI only).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress messages.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Propagate exceptions instead of converting to exit codes.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ensure_gui_dependencies(install_missing=not args.skip_install, verbose=args.verbose)
    except Exception as exc:
        if args.debug:
            raise
        print(f"Error preparing GUI dependencies: {exc}", file=sys.stderr)
        return 1

    if args.deps_only:
        if args.verbose:
            print("[info] Dependencies are ready.")
        return 0

    if args.variant == "simple":
        return launch_simple_gui(verbose=args.verbose, debug=args.debug)

    return launch_full_gui(use_cli=not args.no_cli, verbose=args.verbose, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
