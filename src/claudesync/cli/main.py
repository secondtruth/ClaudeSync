#!/usr/bin/env python3
"""
ClaudeSync v2 CLI - Git-like command structure with full backward compatibility
"""
from __future__ import annotations
import os
import sys
import json
import logging
import click
import click_completion
import subprocess
import urllib.request
import importlib.metadata
from pathlib import Path

from claudesync.configmanager import FileConfigManager, InMemoryConfigManager
from claudesync.utils import handle_errors, validate_and_get_provider
import claudesync.utils as utils
from claudesync.project_instructions import ProjectInstructions
from claudesync.syncmanager import SyncManager

# Import existing command modules
from .auth import auth as auth_module
from .organization import organization as org_module
from .project import project as project_module
from .sync import sync as sync_module, schedule as schedule_module
from .config import config as config_module
from .conflict import conflict as conflict_module
from .chat import chat as chat_module
from .watch import watch as watch_module
from .workspace import workspace as workspace_module
from .pull import pull as pull_command

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
LOG = logging.getLogger("claudesync.cli")

# Initialize click completion
click_completion.init()

# Version
try:
    __version__ = importlib.metadata.version("claudesync")
except Exception:
    __version__ = "0.0.0-dev"

# ---------- Aliased Group ----------
class AliasedGroup(click.Group):
    """A Click Group that supports command aliases and short forms."""
    def __init__(self, *args, aliases: dict[str, str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._aliases = aliases or {}

    def get_command(self, ctx, cmd_name):
        # Direct match
        cmd = click.Group.get_command(self, ctx, cmd_name)
        if cmd:
            return cmd
        # Alias match
        target = self._aliases.get(cmd_name)
        if target:
            return click.Group.get_command(self, ctx, target)
        return None

# Common aliases used across groups
COMMON_ALIASES = {
    "ls": "list",
    "rm": "remove",
    "set_default": "set-default",
}

# ---------- Root CLI ----------
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

@click.group(cls=AliasedGroup, aliases={}, context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cli(ctx):
    """ClaudeSync: Synchronize local files with Claude.ai projects.
    
    Use 'csync' or 'claudesync' to manage your Claude.ai projects from the command line.
    
    Common commands:
      csync auth login         # Authenticate with Claude.ai
      csync project create     # Create a new project
      csync push               # Upload files to Claude.ai
      csync pull               # Download files from Claude.ai
      csync sync               # Bidirectional synchronization
    """
    if ctx.obj is None:
        ctx.obj = FileConfigManager()  # InMemoryConfigManager() for testing

# ---------- Auth Group (using existing auth module) ----------
cli.add_command(auth_module, name="auth")

# ---------- Organization Group (using existing org module with alias) ----------
cli.add_command(org_module, name="organization")
cli.add_command(org_module, name="org")  # Alias

# ---------- Project Group (using existing project module) ----------
cli.add_command(project_module, name="project")

# ---------- Sync Commands ----------


def _filter_existing_files(file_map: dict[str, str], base_path: str) -> dict[str, str]:
    """Drop file entries that no longer exist on disk."""
    filtered: dict[str, str] = {}
    missing: list[str] = []
    for relative_path, file_hash in file_map.items():
        full_path = os.path.join(base_path, relative_path)
        if os.path.exists(full_path):
            filtered[relative_path] = file_hash
        else:
            missing.append(relative_path)
    if missing:
        LOG.debug(
            "Skipping %d missing file(s) during sync: %s",
            len(missing),
            ", ".join(missing[:5]),
        )
    return filtered

cli.add_command(sync_module, name="sync")
cli.add_command(schedule_module, name="schedule")

@cli.command(name="push")
@click.option("--category", help="Specify the file category to sync")
@click.option("--uberproject", is_flag=True, help="Include submodules in parent project sync")
@click.option("--dryrun", is_flag=True, default=False, help="Just show what files would be sent")
@click.option("--dry-run", is_flag=True, default=False, help="Just show what files would be sent")
@click.pass_obj
@handle_errors
def push(config, category, uberproject, dryrun, dry_run):
    '''Push local files to Claude project (upload only).

    For bidirectional sync, use 'csync sync' instead.'''
    # Handle both --dryrun and --dry-run
    dryrun = dryrun or dry_run

    provider = validate_and_get_provider(config, require_project=True)

    if not category:
        category = config.get_default_category()
        if category:
            click.echo(f"Using default category: {category}")

    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    active_project_name = config.get("active_project_name")
    local_path = config.get_local_path()

    if not local_path:
        click.echo(
            "No .claudesync directory found in this directory or any parent directories. "
            "Please run 'csync project create' or 'csync project set' first."
        )
        return

    # Detect if we're in a submodule
    current_dir = Path.cwd()
    submodules = config.get("submodules", [])
    current_submodule = next(
        (
            sm
            for sm in submodules
            if Path(local_path) / sm["relative_path"] == current_dir
        ),
        None,
    )

    if current_submodule:
        # We're in a submodule, so only sync this submodule
        click.echo(
            f"Syncing submodule {current_submodule['active_project_name']} [{current_dir}]"
        )
        sync_submodule(provider, config, current_submodule, category)
    else:
        # Sync main project
        sync_manager = SyncManager(provider, config, config.get_local_path())
        remote_files = provider.list_files(active_organization_id, active_project_id)

        if uberproject:
            # Include submodule files in the parent project
            local_files = utils.get_local_files(
                config, local_path, category, include_submodules=True
            )
        else:
            # Exclude submodule files from the parent project
            local_files = utils.get_local_files(
                config, local_path, category, include_submodules=False
            )

        local_files = _filter_existing_files(local_files, local_path)

        if dryrun:
            for file in local_files.keys():
                try:
                    click.echo(f"Would send file: {file}")
                except UnicodeEncodeError:
                    # Handle emoji/unicode in filenames on Windows
                    safe_name = file.encode("utf-8", errors="replace").decode("utf-8")
                    click.echo(f"Would send file: {safe_name}")
            click.echo("Not sending files due to dry run mode.")
            return

        # Pull project instructions first (always bidirectional for instructions)
        sync_manager._pull_project_instructions(remote_files)

        # Disable two-way sync for push (upload only)
        original_two_way = config.get("two_way_sync", False)
        config.set("two_way_sync", False, local=True)

        sync_manager.sync(local_files, remote_files)

        # Restore original setting
        config.set("two_way_sync", original_two_way, local=True)

        click.echo(
            f"Files pushed successfully to '{active_project_name}': https://claude.ai/project/{active_project_id}"
        )
        click.echo(f"Main project '{active_project_name}' synced successfully")

        # Auto-sync project instructions if enabled
        if config.get('auto_sync_instructions', True):
            instructions = ProjectInstructions(local_path)
            if instructions.is_enabled() and os.path.exists(os.path.join(local_path, instructions.INSTRUCTIONS_FILE)):
                click.echo("\nSyncing project instructions...")
                if instructions.push_instructions(provider, active_organization_id, active_project_id):
                    click.echo("\u2713 Project instructions synced")

        # Always sync submodules to their respective projects
        for submodule in submodules:
            sync_submodule(provider, config, submodule, category)

# Helper function for submodule syncing
def sync_submodule(provider, config, submodule, category):
    submodule_path = Path(config.get_local_path()) / submodule["relative_path"]
    submodule_files = utils.get_local_files(config, str(submodule_path), category)
    submodule_files = _filter_existing_files(submodule_files, str(submodule_path))
    remote_submodule_files = provider.list_files(
        submodule["active_organization_id"], submodule["active_project_id"]
    )

    # Create a new ConfigManager instance for the submodule
    submodule_config = InMemoryConfigManager()
    submodule_config.load_from_file_config(config)
    submodule_config.set(
        "active_project_id", submodule["active_project_id"], local=True
    )
    submodule_config.set(
        "active_project_name", submodule["active_project_name"], local=True
    )

    # Create a new SyncManager for the submodule
    submodule_sync_manager = SyncManager(
        provider, submodule_config, str(submodule_path)
    )

    submodule_sync_manager.sync(submodule_files, remote_submodule_files)
    click.echo(
        f"Submodule '{submodule['active_project_name']}' synced successfully: "
        f"https://claude.ai/project/{submodule['active_project_id']}"
    )

cli.add_command(pull_command, name="pull")

# ---------- Config Group (using existing config module) ----------

cli.add_command(config_module, name="config")

# ---------- Conflict Group (using existing conflict module) ----------
cli.add_command(conflict_module, name="conflict")

# ---------- Chat Group (using existing chat module) ----------
cli.add_command(chat_module, name="chat")

# ---------- Workspace Group (using existing workspace module) ----------
cli.add_command(workspace_module, name="workspace")

# ---------- Watch Group (using existing watch module) ----------
cli.add_command(watch_module, name="watch")

# ---------- GUI Group ----------
@cli.group(cls=AliasedGroup, aliases=COMMON_ALIASES, name="gui")
def gui_group():
    """GUI launcher."""
    pass

@gui_group.command(name="launch")
@click.option("--simple", is_flag=True, help="Launch simple GUI")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def gui_launch(simple, debug):
    """Launch the ClaudeSync GUI interface."""
    try:
        from claudesync.gui.main import run_gui
        click.echo("Launching ClaudeSync GUI...")
        run_gui(simple=simple, debug=debug)
    except ImportError:
        click.echo("GUI module not found. Please ensure tkinter is installed.")
    except Exception as e:
        click.echo(f"Failed to launch GUI: {str(e)}")

# ---------- Utils Group ----------
@cli.group(cls=AliasedGroup, aliases=COMMON_ALIASES, name="utils")
def utils_group():
    """Utility commands."""
    pass

@utils_group.command(name="upgrade")
@click.pass_context
def utils_upgrade(ctx):
    """Upgrade ClaudeSync to the latest version."""
    current_version = __version__

    # Check for the latest version
    try:
        with urllib.request.urlopen(
            "https://pypi.org/pypi/claudesync/json"
        ) as response:
            data = json.loads(response.read())
            latest_version = data["info"]["version"]

        if current_version == latest_version:
            click.echo(
                f"You are already on the latest version of ClaudeSync (v{current_version})."
            )
            return
    except Exception as e:
        click.echo(f"Unable to check for the latest version: {str(e)}")
        click.echo("Proceeding with the upgrade process.")
        latest_version = "latest"

    # Upgrade ClaudeSync
    click.echo(f"Upgrading ClaudeSync from v{current_version} to v{latest_version}...")
    try:
        subprocess.run(["pip", "install", "--upgrade", "claudesync"], check=True)
        click.echo("ClaudeSync has been successfully upgraded.")
    except subprocess.CalledProcessError:
        click.echo(
            "Failed to upgrade ClaudeSync. Please try manually: pip install --upgrade claudesync"
        )

    # Inform user about the upgrade process
    click.echo("\nUpgrade process completed:")
    click.echo(
        f"1. ClaudeSync has been upgraded from v{current_version} to v{latest_version}."
    )
    click.echo("2. Your session key has been preserved (if it existed and was valid).")
    click.echo(
        "\nPlease run 'csync auth login' to complete your configuration setup if needed."
    )

@utils_group.command(name="doctor")
@click.pass_obj
def utils_doctor(config):
    """Run system diagnostics to check ClaudeSync configuration and health."""
    import platform
    import shutil
    from pathlib import Path
    
    click.echo("🔍 ClaudeSync System Diagnostics\n")
    click.echo("=" * 50)
    
    # System Information
    click.echo("\n📊 System Information:")
    click.echo(f"  • Platform: {platform.system()} {platform.release()}")
    click.echo(f"  • Python: {platform.python_version()}")
    click.echo(f"  • ClaudeSync: {__version__}")
    
    # Authentication Status
    click.echo("\n🔐 Authentication:")
    session_key = config.get_session_key('claude.ai')
    if session_key:
        click.echo("  ✅ Session key found")
        try:
            from claudesync.provider_factory import get_provider
            provider = get_provider(config, 'claude.ai')
            orgs = provider.get_organizations()
            click.echo(f"  ✅ Access to {len(orgs)} organization(s)")
        except Exception as e:
            click.echo(f"  ⚠️ Session validation failed: {str(e)}")
    else:
        click.echo("  ❌ No session key found - run 'csync auth login'")
    
    # Configuration
    click.echo("\n⚙️ Configuration:")
    active_org = config.get("active_organization_id")
    active_project = config.get("active_project_id")
    click.echo(f"  • Active Org: {'✅ Set' if active_org else '❌ Not set'}")
    click.echo(f"  • Active Project: {'✅ Set' if active_project else '❌ Not set'}")
    
    # Local Project
    click.echo("\n📁 Local Project:")
    local_path = config.get_local_path()
    if local_path:
        click.echo(f"  ✅ Project directory: {local_path}")
        claudesync_dir = Path(local_path) / ".claudesync"
        if claudesync_dir.exists():
            click.echo("  ✅ .claudesync directory found")
        else:
            click.echo("  ⚠️ .claudesync directory missing")
    else:
        click.echo("  ❌ No local project configured")
    
    # Dependencies
    click.echo("\n📦 Dependencies:")
    deps = ['click', 'click_completion', 'pathspec', 'tqdm', 'sseclient_py']
    for dep in deps:
        try:
            __import__(dep.replace('-', '_'))
            click.echo(f"  ✅ {dep}")
        except ImportError:
            click.echo(f"  ❌ {dep} - missing")
    
    # Optional Features
    click.echo("\n🎯 Optional Features:")
    try:
        import tkinter
        click.echo("  ✅ GUI support (tkinter)")
    except ImportError:
        click.echo("  ❌ GUI support (tkinter not installed)")
    
    # Commands Available
    click.echo("\n🛠️ Commands Available:")
    for cmd_name in ['git', 'pip', 'python3']:
        if shutil.which(cmd_name):
            click.echo(f"  ✅ {cmd_name}")
        else:
            click.echo(f"  ⚠️ {cmd_name} not found in PATH")
    
    click.echo("\n" + "=" * 50)
    click.echo("Diagnostics complete. Fix any ❌ issues for optimal performance.")


# Legacy upgrade command (top-level)

@cli.command(name="upgrade")
@click.pass_context
def legacy_upgrade(ctx):
    """Upgrade ClaudeSync to the latest version."""
    ctx.invoke(utils_upgrade)

# Install completion command
@cli.command()
@click.argument(
    "shell", required=False, type=click.Choice(["bash", "zsh", "fish", "powershell"])
)
def install_completion(shell):
    """Install completion for the specified shell."""
    if shell is None:
        shell = click_completion.get_auto_shell()
        click.echo("Shell is set to '%s'" % shell)
    click_completion.install(shell=shell)
    click.echo("Completion installed.")

# Embedding command
@cli.command()
@click.option("--category", help="Specify the file category to sync")
@click.option("--uberproject", is_flag=True, help="Include submodules in the parent project sync")
@click.pass_obj
@handle_errors
def embedding(config, category, uberproject):
    """Generate a text embedding from the project."""
    if not category:
        category = config.get_default_category()
        if category:
            click.echo(f"Using default category: {category}")

    local_path = config.get_local_path()

    if not local_path:
        click.echo(
            "No .claudesync directory found in this directory or any parent directories. "
            "Please run 'csync project create' or 'csync project set' first."
        )
        return

    # Sync main project
    sync_manager = SyncManager(None, config, config.get_local_path())

    if uberproject:
        # Include submodule files in the parent project
        local_files = utils.get_local_files(
            config, local_path, category, include_submodules=True
        )
    else:
        # Exclude submodule files from the parent project
        local_files = utils.get_local_files(
            config, local_path, category, include_submodules=False
        )

    output = sync_manager.embedding(local_files)
    click.echo(f"{output}")

def main():
    """Main entry point supporting both claudesync and csync commands."""
    cli(prog_name="csync" if "csync" in sys.argv[0] else "claudesync")

if __name__ == "__main__":
    main()
