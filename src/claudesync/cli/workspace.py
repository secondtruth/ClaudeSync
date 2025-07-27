import click
import json
import os
from ..workspace_config import WorkspaceConfig
from ..workspace_manager import WorkspaceManager
from ..utils import handle_errors

@click.group()
def workspace():
    """Manage workspace with multiple ClaudeSync projects."""
    pass

@workspace.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_obj
@handle_errors
def set_root(config, path):
    """Set the workspace root directory."""
    ws_config = WorkspaceConfig()
    ws_config.set_workspace_root(path)
    click.echo(f"Workspace root set to: {os.path.abspath(path)}")
    
    # Discover projects
    manager = WorkspaceManager(ws_config)
    projects = manager.discover_projects()
    
    if projects:
        click.echo(f"\nFound {len(projects)} project(s):")
        for project in projects:
            click.echo(f"  - {project['name']} at {project['relative_path']}")
    else:
        click.echo("\nNo ClaudeSync projects found in workspace.")

@workspace.command()
@click.pass_obj
@handle_errors
def config(config):
    """Show workspace configuration."""
    ws_config = WorkspaceConfig()
    config_data = ws_config.get_config()
    
    click.echo("Workspace Configuration:")
    click.echo(json.dumps(config_data, indent=2))

@workspace.command()
@click.pass_obj
@handle_errors
def reset(config):
    """Reset workspace configuration to defaults."""
    if click.confirm("This will reset all workspace settings. Continue?"):
        ws_config = WorkspaceConfig()
        ws_config.reset()
        click.echo("Workspace configuration reset to defaults.")

@workspace.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_obj
@handle_errors
def discover(config, output_json):
    """Discover all ClaudeSync projects in workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if output_json:
        click.echo(json.dumps(projects, indent=2))
    else:
        if not projects:
            click.echo("No ClaudeSync projects found.")
            if not ws_config.get_workspace_root():
                click.echo("Tip: Set a workspace root with 'claudesync workspace set-root <path>'")
        else:
            click.echo(f"Found {len(projects)} project(s):")
            for project in projects:
                click.echo(f"\n  {project['name']}")
                click.echo(f"    Path: {project['path']}")
                click.echo(f"    ID: {project['id']}")

@workspace.command()
@click.option('--sequential', is_flag=True, help='Sync projects one at a time')
@click.option('--dry-run', is_flag=True, help='Show what would be synced')
@click.pass_obj
@handle_errors
def sync_all(config, sequential, dry_run):
    """Sync all projects in the workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if not projects:
        click.echo("No projects found to sync.")
        return
    
    click.echo(f"Found {len(projects)} project(s) to sync.")
    
    if not dry_run and not click.confirm("Continue with sync?"):
        return
    
    # Perform sync
    results = manager.sync_all_projects(
        projects,
        parallel=not sequential,
        dry_run=dry_run
    )
    
    if dry_run:
        return
    
    # Show results
    click.echo("\nSync Results:")
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] in ['failed', 'error', 'timeout'])
    
    for result in results:
        if result['status'] == 'success':
            click.echo(f"  ✓ {result['project']} ({result['duration']:.1f}s)")
        else:
            click.echo(f"  ✗ {result['project']}: {result['message']}")
    
    click.echo(f"\nSummary: {success_count} succeeded, {failed_count} failed")

@workspace.command()
@click.option('--dry-run', is_flag=True, help='Preview what will be downloaded')
@click.option('--backup-existing', is_flag=True, help='Backup existing chat files')
@click.pass_obj
@handle_errors
def chat_pull_all(config, dry_run, backup_existing):
    """Pull chats for all projects in workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if not projects:
        click.echo("No projects found.")
        return
    
    click.echo(f"Found {len(projects)} project(s).")
    
    if not dry_run and not click.confirm("Pull chats for all projects?"):
        return
    
    # Pull chats
    safety_options = {
        'dry_run': dry_run,
        'backup_existing': backup_existing
    }
    
    results = manager.pull_all_chats(projects, safety_options)
    
    # Show results
    click.echo("\nChat Pull Results:")
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] in ['failed', 'error'])
    
    for result in results:
        if result['status'] == 'success':
            click.echo(f"  ✓ {result['project']}")
        else:
            click.echo(f"  ✗ {result['project']}: {result['message']}")
    
    click.echo(f"\nSummary: {success_count} succeeded, {failed_count} failed")

@workspace.command()
@click.pass_obj
@handle_errors
def status(config):
    """Show workspace status overview."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    status = manager.get_status()
    
    click.echo(f"Workspace Status")
    click.echo(f"================")
    click.echo(f"Root: {status['workspace_root']}")
    click.echo(f"Projects: {status['total_projects']}")
    
    if status['projects']:
        click.echo("\nProject Details:")
        for project in status['projects']:
            watcher_icon = "👁️ " if project['watcher'] == 'running' else "  "
            click.echo(f"  {watcher_icon}{project['name']}")
            click.echo(f"     Path: {project['path']}")
            click.echo(f"     Watcher: {project['watcher']}")