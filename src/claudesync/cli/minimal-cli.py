#!/usr/bin/env python3
"""
ClaudeSync Minimal CLI - Just 4 commands for workspace-wide sync.
"""
import sys
from pathlib import Path

import click

from claudesync.provider_factory import get_provider
from claudesync.workspace_sync import WorkspaceSync
from claudesync.configmanager import FileConfigManager


def get_provider_with_auth():
    """Get authenticated provider instance."""
    config = FileConfigManager()

    # Check for existing auth using config manager
    session_key, expiry = config.get_session_key("claude.ai")

    if not session_key:
        click.echo("X Not authenticated. Run: csync auth login")
        sys.exit(1)

    # Get provider (claude.ai)
    provider = get_provider(config, "claude.ai")
    
    return provider, config


@click.group(invoke_without_command=False)
@click.version_option()
def cli():
    """ClaudeSync - Workspace-wide sync for ALL Claude.ai projects."""
    pass


@cli.group()
def auth():
    """Authentication commands."""
    pass


@auth.command()
@click.option('--session-key', help='Provide session key directly')
def login(session_key):
    """Login to Claude.ai using session key."""
    config = FileConfigManager()
    provider = get_provider(config, "claude.ai")

    try:
        if session_key:
            # Validate session key format
            if not session_key.startswith("sk-ant"):
                click.echo("X Invalid session key format. Must start with 'sk-ant'")
                return
            # Set provided session key for non-interactive login
            provider._auto_approve_expiry = True
            provider._provided_session_key = session_key

        # Login (will use provided key if set)
        session_key_result, expiry = provider.login()
        config.set_session_key("claude.ai", session_key_result, expiry)

        click.echo("OK Authenticated successfully!")
    except Exception as e:
        click.echo(f"X Authentication failed: {e}")


@auth.command()
def logout():
    """Logout and clear credentials."""
    config = FileConfigManager()
    config.clear_all_session_keys()
    click.echo("OK Logged out successfully.")


@auth.command()
def status():
    """Check authentication status."""
    config = FileConfigManager()
    session_key, expiry = config.get_session_key("claude.ai")

    if session_key:
        # Try to validate by getting orgs
        try:
            provider = get_provider(config, "claude.ai")
            orgs = provider.get_organizations()
            
            if orgs:
                click.echo(f"OK Authenticated to {len(orgs)} organization(s)")
                for org in orgs[:3]:  # Show first 3
                    click.echo(f"  - {org['name']}")
            else:
                click.echo("! Authenticated but no organizations found")
        except Exception as e:
            click.echo(f"X Session invalid: {e}")
    else:
        click.echo("X Not authenticated")


@cli.group()
def workspace():
    """Workspace sync commands."""
    pass


@workspace.command()
@click.argument('path', type=click.Path(), default='.')
def init(path):
    """Initialize a workspace root directory."""
    workspace_path = Path(path).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Save to central config
    config_dir = Path.home() / ".claudesync"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "workspace.json"
    
    import json
    config = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    config["workspace_root"] = str(workspace_path)
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    click.echo(f"OK Workspace initialized at: {workspace_path}")


@workspace.command()
@click.option('--dry-run', is_flag=True, help='Show what would be synced without doing it')
def sync(dry_run):
    """Sync ALL Claude.ai projects to workspace folders."""
    # Load workspace config
    config_file = Path.home() / ".claudesync" / "workspace.json"
    
    if not config_file.exists():
        click.echo("X No workspace configured. Run: csync workspace init [path]")
        sys.exit(1)
    
    import json
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    workspace_root = Path(config.get("workspace_root", "."))
    
    # Get authenticated provider
    provider, _ = get_provider_with_auth()
    
    # Create sync manager
    syncer = WorkspaceSync(workspace_root, provider)
    
    # Run sync
    click.echo(f"Syncing workspace: {workspace_root}\n")
    
    stats = syncer.sync_all(dry_run=dry_run)
    
    # Show results
    click.echo(f"\nOK Sync complete!")
    click.echo(f"  - Created: {stats['created']} projects")
    click.echo(f"  - Updated: {stats['updated']} projects")
    click.echo(f"  - Skipped: {stats['skipped']} projects")
    
    if stats['errors'] > 0:
        click.echo(f"  - ! Errors: {stats['errors']} projects")


@workspace.command()
@click.option('--detailed', is_flag=True, help='Show detailed project list')
def status(detailed):
    """Show workspace sync status."""
    # Load workspace config
    config_file = Path.home() / ".claudesync" / "workspace.json"
    
    if not config_file.exists():
        click.echo("X No workspace configured. Run: csync workspace init [path]")
        sys.exit(1)
    
    import json
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    workspace_root = Path(config.get("workspace_root", "."))
    
    # Create sync manager (no auth needed for status)
    from unittest.mock import Mock
    mock_provider = Mock()  # Status doesn't need provider
    syncer = WorkspaceSync(workspace_root, mock_provider)
    
    # Get status
    status_info = syncer.status()
    
    click.echo(f"Workspace Status")
    click.echo(f"  - Root: {status_info['workspace_root']}")
    click.echo(f"  - Tracked projects: {status_info['total_projects']}")
    click.echo(f"  - Local folders: {status_info['local_folders']}")
    
    if status_info['last_sync']:
        click.echo(f"  - Last sync: {status_info['last_sync']}")
    else:
        click.echo(f"  - Last sync: Never")
    
    if status_info['orphaned_folders']:
        click.echo(f"\n!  Orphaned folders (not tracked):")
        for folder in status_info['orphaned_folders']:
            click.echo(f"  - {folder}")
    
    if detailed:
        click.echo(f"\n📁 Project Details:")
        projects = syncer.list_projects()
        for project in projects:
            status_icon = "OK" if project['exists'] else "X"
            click.echo(f"  {status_icon} {project['folder']}")
            if 'name' in project:
                click.echo(f"      Name: {project['name']}")
            if 'synced_at' in project:
                click.echo(f"      Synced: {project['synced_at']}")


# Aliases for backward compatibility (hidden)
@cli.command(hidden=True)
@click.pass_context
def push(ctx):
    """Legacy push command - redirects to sync."""
    click.echo("Note: 'push' is deprecated. Using 'workspace sync' instead.\n")
    ctx.invoke(sync)


@cli.command(hidden=True)
@click.pass_context
def pull(ctx):
    """Legacy pull command - redirects to sync."""
    click.echo("Note: 'pull' is deprecated. Using 'workspace sync' instead.\n")
    ctx.invoke(sync)


if __name__ == '__main__':
    cli()