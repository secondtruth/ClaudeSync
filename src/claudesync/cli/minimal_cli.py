#!/usr/bin/env python3
"""
ClaudeSync Minimal CLI - Just 4 commands for workspace-wide sync.
"""
import sys
from pathlib import Path

import click

from claudesync.provider_factory import get_provider
from claudesync.workspace_sync import WorkspaceSync, safe_print
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
    """ClaudeSync - Workspace-wide sync for ALL Claude.ai projects.

    \b
    AUTHENTICATION:
      csync auth login --session-key <key>  Login with Claude.ai session key
      csync auth logout                     Logout from Claude.ai
      csync auth status                     Check authentication status

    \b
    WORKSPACE MANAGEMENT:
      csync workspace init <path>           Initialize workspace directory
      csync workspace sync                  Sync all projects (download only)
          --bidirectional                   Enable two-way sync
          --chats                           Include chat conversations
          --conflict <strategy>             Conflict resolution (remote/local/newer)
          --dry-run                         Preview changes without syncing
      csync workspace status                Show workspace sync status
      csync workspace diff                  Audit differences between local and remote
          --detailed                        Show file-level differences
          --json                            Output as JSON

    \b
    GUI:
      csync gui                             Launch system tray application

    \b
    QUICK START:
      1. csync auth login --session-key sk-ant-...
      2. csync workspace init ~/ClaudeProjects
      3. csync workspace sync

    \b
    EXAMPLES:
      csync workspace sync --bidirectional --chats
      csync workspace sync --conflict newer --dry-run
      csync gui  # Launch system tray for background sync
    """
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
@click.option('--detailed', is_flag=True, help='Show detailed file differences')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.option('--save-report', is_flag=True, help='Save detailed report to workspace root')
def diff(detailed, output_json, save_report):
    """Audit differences between local workspace and Claude.ai projects."""
    # Load workspace config
    config_file = Path.home() / ".claudesync" / "workspace.json"

    if not config_file.exists():
        click.echo("X No workspace configured. Run: csync workspace init [path]")
        sys.exit(1)

    import json
    from datetime import datetime
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    workspace_root = config.get("workspace_root")
    if not workspace_root:
        click.echo("X No workspace root configured")
        sys.exit(1)

    # Get provider and check auth
    provider, _ = get_provider_with_auth()

    # Create workspace syncer
    syncer = WorkspaceSync(workspace_root, provider)

    # Get diff analysis (always detailed if saving report)
    diff_info = syncer.analyze_diff(provider, detailed or save_report)

    # Save detailed report if requested
    if save_report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"workspace_diff_report_{timestamp}.md"
        report_path = Path(workspace_root) / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# Workspace Diff Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Workspace:** {workspace_root}\n\n")

            # Summary section
            f.write(f"## Summary\n\n")
            f.write(f"- Remote projects: {diff_info['summary']['remote_projects']}\n")
            f.write(f"- Local folders: {diff_info['summary']['local_folders']}\n")
            f.write(f"- Matched projects: {diff_info['summary']['matched']}\n")
            f.write(f"- Remote only: {diff_info['summary']['remote_only']}\n")
            f.write(f"- Local only: {diff_info['summary']['local_only']}\n\n")

            # Remote-only projects
            if diff_info['remote_only']:
                f.write(f"## Remote-Only Projects ({len(diff_info['remote_only'])})\n\n")
                f.write("These projects exist on Claude.ai but not in your local workspace.\n\n")
                for project in diff_info['remote_only']:
                    f.write(f"### {project['name']}\n")
                    f.write(f"- **Project ID:** `{project['id']}`\n")
                    f.write(f"- **Sanitized name:** `{project['sanitized_name']}`\n")
                    if 'file_count' in project:
                        f.write(f"- **Files:** {project['file_count']}\n")
                    f.write(f"\n")

            # Local-only folders
            if diff_info['local_only']:
                f.write(f"## Local-Only Folders ({len(diff_info['local_only'])})\n\n")
                f.write("These folders exist locally but are not tracked in the project map.\n\n")
                for folder in diff_info['local_only']:
                    f.write(f"- `{folder}`\n")
                f.write(f"\n")

            # Matched projects with details
            if diff_info['matched']:
                f.write(f"## Matched Projects ({len(diff_info['matched'])})\n\n")
                for match in diff_info['matched']:
                    f.write(f"### {match['name']}\n")
                    f.write(f"- **Project ID:** `{match['id']}`\n")
                    f.write(f"- **Local folder:** `{match['folder']}`\n")
                    f.write(f"- **Status:** {'⚠️ Has differences' if match['has_differences'] else '✅ In sync'}\n")

                    if match['remote_only_files']:
                        f.write(f"\n**Remote-only files ({len(match['remote_only_files'])}):**\n")
                        for fname in match['remote_only_files']:
                            f.write(f"  - ➕ `{fname}`\n")

                    if match['local_only_files']:
                        f.write(f"\n**Local-only files ({len(match['local_only_files'])}):**\n")
                        for fname in match['local_only_files']:
                            f.write(f"  - ➖ `{fname}`\n")

                    if match['modified_files']:
                        f.write(f"\n**Modified files ({len(match['modified_files'])}):**\n")
                        for fname in match['modified_files']:
                            f.write(f"  - ✏️ `{fname}`\n")

                    f.write(f"\n")

            # Recommendations
            f.write(f"## Recommendations\n\n")
            if diff_info['remote_only']:
                f.write(f"- Run `csync workspace sync` to download missing projects\n")
            if diff_info['summary']['local_only'] > 0:
                f.write(f"- Run `csync workspace sync --bidirectional` to upload local folders\n")
            if any(m['has_differences'] for m in diff_info['matched']):
                f.write(f"- Run `csync workspace sync --bidirectional --conflict newer` to sync changes\n")

        click.echo(f"✅ Report saved to: {report_path}")

    if output_json:
        click.echo(json.dumps(diff_info, indent=2, ensure_ascii=False))
    else:
        # Display human-readable diff
        click.echo("\n=== WORKSPACE DIFF ANALYSIS ===\n")

        # Summary
        click.echo(f"Workspace: {workspace_root}")
        click.echo(f"Remote projects: {diff_info['summary']['remote_projects']}")
        click.echo(f"Local folders: {diff_info['summary']['local_folders']}")
        click.echo(f"Matched: {diff_info['summary']['matched']}")
        click.echo(f"Remote only: {diff_info['summary']['remote_only']}")
        click.echo(f"Local only: {diff_info['summary']['local_only']}")

        # Projects only on remote
        if diff_info['remote_only']:
            click.echo(f"\n[DOWNLOAD] Projects on Claude.ai NOT in local workspace ({len(diff_info['remote_only'])}):")
            for project in diff_info['remote_only']:
                safe_print(f"  - {project['name']}")
                if detailed and project.get('file_count'):
                    click.echo(f"    Files: {project['file_count']}")

        # Folders only on local
        if diff_info['local_only']:
            click.echo(f"\n[UPLOAD] Local folders NOT on Claude.ai ({len(diff_info['local_only'])}):")
            for folder in diff_info['local_only']:
                safe_print(f"  - {folder}")

        # Matched but different
        if diff_info['matched']:
            click.echo(f"\n[SYNC] Matched projects with differences ({len(diff_info['matched'])}):")
            for match in diff_info['matched']:
                if match['has_differences']:
                    safe_print(f"  - {match['name']}")
                    if match['remote_only_files']:
                        click.echo(f"    Remote only: {len(match['remote_only_files'])} files")
                        if detailed:
                            for f in match['remote_only_files'][:5]:
                                click.echo(f"      + {f}")
                    if match['local_only_files']:
                        click.echo(f"    Local only: {len(match['local_only_files'])} files")
                        if detailed:
                            for f in match['local_only_files'][:5]:
                                click.echo(f"      - {f}")
                    if match['modified_files']:
                        click.echo(f"    Modified: {len(match['modified_files'])} files")
                        if detailed:
                            for f in match['modified_files'][:5]:
                                click.echo(f"      * {f}")
                elif not detailed:
                    safe_print(f"  OK {match['name']} (in sync)")

        # Recommendations
        click.echo("\n[RECOMMENDATIONS]")
        if diff_info['remote_only']:
            click.echo("  - Run 'csync workspace sync' to download missing projects")
        if diff_info['summary']['local_only'] > 0:
            click.echo("  - Run 'csync workspace sync --bidirectional' to upload local folders")
        if any(m['has_differences'] for m in diff_info['matched']):
            click.echo("  - Run 'csync workspace sync --bidirectional --conflict newer' to sync changes")


@cli.command()
def gui():
    """Launch ClaudeSync GUI system tray application."""
    try:
        from claudesync.gui.systray import main
        main()
    except ImportError as e:
        click.echo(f"X GUI requires PyQt6: {e}")
        click.echo("Install with: pip install PyQt6")
        sys.exit(1)


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
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    
    config["workspace_root"] = str(workspace_path)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    click.echo(f"OK Workspace initialized at: {workspace_path}")


@workspace.command()
@click.option('--dry-run', is_flag=True, help='Show what would be synced without doing it')
@click.option('--bidirectional', is_flag=True, help='Also upload local changes to Claude.ai')
@click.option('--chats', is_flag=True, help='Also sync chat conversations')
@click.option('--conflict', type=click.Choice(['remote', 'local', 'newer']), default='remote',
              help='How to resolve conflicts (default: remote)')
def sync(dry_run, bidirectional, chats, conflict):
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
    
    stats = syncer.sync_all(
        dry_run=dry_run,
        bidirectional=bidirectional,
        sync_chats=chats,
        conflict_strategy=conflict
    )

    # Show results
    click.echo(f"\nOK Sync complete!")
    click.echo(f"  - Created: {stats['created']} projects")
    click.echo(f"  - Updated: {stats['updated']} projects")
    click.echo(f"  - Skipped: {stats['skipped']} projects")

    if bidirectional:
        click.echo(f"  - Uploaded: {stats.get('uploaded', 0)} files")
        click.echo(f"  - Conflicts: {stats.get('conflicts', 0)} resolved")

    if chats:
        click.echo(f"  - Chats: {stats.get('chats', 0)} synced")

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