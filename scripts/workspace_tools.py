#!/usr/bin/env python3
"""Workspace maintenance utilities for ClaudeSync."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

GLOBAL_CONFIG_NAME = ".claudesync-workspace.json"
LOCAL_CONFIG_NAME = "config.local.json"


@dataclass
class FixResult:
    """Summary of performed workspace fixes."""

    checked_projects: int = 0
    fixes_applied: int = 0


def fix_workspace(workspace_root: Path, dry_run: bool = False) -> FixResult:
    """Resolve common workspace problems and return a summary."""
    workspace_root = workspace_root.expanduser().resolve()
    result = FixResult()

    if not workspace_root.exists():
        raise FileNotFoundError(f"Workspace not found: {workspace_root}")

    for project_dir in workspace_root.iterdir():
        if not project_dir.is_dir():
            continue

        result.checked_projects += 1
        print(f"\nChecking {project_dir}")

        double_claudesync = project_dir / ".claudesync" / ".claudesync"
        if double_claudesync.exists():
            print("  Found nested .claudesync directory")
            inner_config = double_claudesync / LOCAL_CONFIG_NAME
            outer_config = project_dir / ".claudesync" / LOCAL_CONFIG_NAME

            if inner_config.exists() and not outer_config.exists():
                print("  Moving inner config to outer directory")
                if not dry_run:
                    outer_config.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(inner_config), str(outer_config))
                result.fixes_applied += 1

            print("  Removing nested .claudesync directory")
            if not dry_run:
                shutil.rmtree(double_claudesync)
            result.fixes_applied += 1

        config_file = project_dir / ".claudesync" / LOCAL_CONFIG_NAME
        if config_file.exists():
            try:
                config_data = json.loads(config_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                print(f"  [warn] Failed to read {config_file}: {exc}")
                continue

            if config_data.get("local_path") != str(project_dir):
                print("  Correcting local_path in config.local.json")
                config_data["local_path"] = str(project_dir)
                if not dry_run:
                    config_file.write_text(
                        json.dumps(config_data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                result.fixes_applied += 1

    print(
        f"\nFix summary: checked {result.checked_projects} project(s), "
        f"applied {result.fixes_applied} fix(es)."
    )
    if dry_run:
        print("No changes were written due to --dry-run.")

    return result


def migrate_to_global_config(
    workspace_root: Path, remove_old: bool = False
) -> Tuple[Path, int]:
    """Create the consolidated workspace config file."""
    workspace_root = workspace_root.expanduser().resolve()
    if not workspace_root.exists():
        raise FileNotFoundError(f"Workspace not found: {workspace_root}")

    global_config_path = workspace_root / GLOBAL_CONFIG_NAME
    global_config: Dict[str, object] = {
        "version": "3.0.0",
        "workspace_root": str(workspace_root),
        "global_settings": {
            "active_provider": "claude.ai",
            "upload_delay": 0.5,
            "max_file_size": 32768,
            "compression_algorithm": "none",
            "two_way_sync": True,
            "prune_remote_files": True,
            "conflict_strategy": "prompt",
        },
        "projects": {},
    }

    migrated = 0
    for config_dir in workspace_root.rglob(".claudesync"):
        if not config_dir.is_dir():
            continue
        project_dir = config_dir.parent
        config_file = config_dir / LOCAL_CONFIG_NAME
        if not config_file.exists():
            continue
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[warn] Failed to parse {config_file}: {exc}")
            continue

        project_id = data.get("active_project_id")
        if not project_id:
            print(f"[skip] Missing project id in {config_file}")
            continue

        project_name = data.get("active_project_name", project_dir.name)
        global_config["projects"][project_id] = {
            "name": project_name,
            "id": project_id,
            "local_path": str(project_dir),
            "organization_id": data.get("active_organization_id"),
            "enabled": True,
        }

        org_id = data.get("active_organization_id")
        if org_id and not global_config["global_settings"].get("active_organization_id"):
            global_config["global_settings"]["active_organization_id"] = org_id

        migrated += 1
        print(f"[ok] Migrated {project_name} ({project_id})")

        if remove_old:
            shutil.rmtree(config_dir, ignore_errors=True)
            print(f"      Removed {config_dir}")

    if migrated:
        global_config_path.write_text(
            json.dumps(global_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            f"\n[done] Wrote {GLOBAL_CONFIG_NAME} with {migrated} project(s) at "
            f"{global_config_path}"
        )
    else:
        print("No projects found to migrate.")

    return global_config_path, migrated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fix_parser = subparsers.add_parser("fix", help="Repair common workspace issues.")
    fix_parser.add_argument(
        "workspace",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Workspace root (defaults to current directory)",
    )
    fix_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned fixes without writing changes.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate", help="Create or refresh the consolidated workspace config."
    )
    migrate_parser.add_argument(
        "workspace",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Workspace root (defaults to current directory)",
    )
    migrate_parser.add_argument(
        "--remove-old",
        action="store_true",
        help="Delete per-project .claudesync directories after migration.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "fix":
            fix_workspace(args.workspace, dry_run=args.dry_run)
            return 0
        if args.command == "migrate":
            migrate_to_global_config(args.workspace, remove_old=args.remove_old)
            return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    parser.error("No command provided")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

