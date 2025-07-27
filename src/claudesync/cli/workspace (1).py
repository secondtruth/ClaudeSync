"""
Workspace CLI commands for ClaudeSync.
Provides multi-project operations without hardcoded paths.
"""

import click
import os
from pathlib import Path
from ..workspace_manager import WorkspaceManager, get_default_search_paths
from ..workspace_config import WorkspaceConfig
from ..utils import handle_errors

@click.group()
def workspace():
    """Multi-project workspace management."""
    pass


@workspace.command()
@click.option(
    "--search-path", 
    multiple=True,
    help="Additional directories to search for projects (can be used multiple times)"
)
@click.option(
    "--max-depth",
    default=3,
    help="Maximum depth to search for projects (default: 3)"
)
@handle_errors
def discover(search_path, max_depth):
    """Discover all ClaudeSync projects in common directories."""
    
    # Build search paths
    search_paths = list(search_path) if search_path else []
    
    # Add default paths if no custom paths specified
    if not search_paths:
        search_paths = get_default_search_paths()
        click.echo("🔍 Using default search paths:")
        for path in search_paths:
            click.echo(f"  📁 {path}")
    else:
        click.echo("🔍 Searching custom paths:")
        for path in search_paths:
            click.echo(f"  📁 {path}")
    
    click.echo("")
    
    # Discover projects
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, max_depth)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        click.echo("\n💡 Tips:")
        click.echo("  • Make sure you have created projects with 'claudesync project create'")
        click.echo("  • Use --search-path to specify custom directories")
        click.echo("  • Increase --max-depth if projects are deeply nested")
        return
    
    click.echo(f"✅ Found {len(projects)} ClaudeSync projects:")
    for project in projects:
        click.echo(f"  📋 {project.name}")
        click.echo(f"     📁 {project.path}")
    
    click.echo(f"\n💡 Next steps:")
    click.echo(f"  claudesync workspace sync-all     # Sync all {len(projects)} projects")
    click.echo(f"  claudesync workspace chat-pull-all # Pull chats for all projects")


@workspace.command()
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects (uses defaults if not specified)"
)
@click.option(
    "--max-depth",
    default=3,
    help="Maximum depth to search for projects (default: 3)"
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=True,
    help="Continue syncing other projects if one fails (default: true)"
)
@handle_errors
def sync_all(search_path, max_depth, continue_on_error):
    """Sync all discovered ClaudeSync projects."""
    
    # Build search paths
    search_paths = list(search_path) if search_path else get_default_search_paths()
    
    click.echo("🔄 Starting workspace sync...")
    click.echo(f"🔍 Searching in {len(search_paths)} directories...")
    
    # Discover and sync projects
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, max_depth)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        click.echo("💡 Run 'claudesync workspace discover' to see available projects")
        return
    
    click.echo(f"📋 Found {len(projects)} projects to sync")
    click.echo("")
    
    # Sync all projects
    results = manager.sync_all_projects(projects)
    
    # Report results
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    click.echo("")
    click.echo("📊 Sync Summary:")
    click.echo(f"  ✅ Successful: {successful}")
    click.echo(f"  ❌ Failed: {failed}")
    click.echo(f"  📋 Total: {len(results)}")
    
    if failed > 0:
        click.echo("\n❌ Failed projects:")
        for name, success in results.items():
            if not success:
                click.echo(f"  • {name}")
        
        if not continue_on_error:
            exit(1)


@workspace.command()
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects (uses defaults if not specified)"
)
@click.option(
    "--max-depth",
    default=3,
    help="Maximum depth to search for projects (default: 3)"
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    default=True,
    help="Continue with other projects if one fails (default: true)"
)
@click.option(
    "--dry-run", 
    is_flag=True, 
    help="Preview what will be downloaded without making changes"
)
@click.option(
    "--backup-existing", 
    is_flag=True, 
    help="Create backup of existing chat files before overwriting"
)
@click.option(
    "--force", 
    is_flag=True, 
    help="Skip confirmation prompts and proceed with download"
)
@handle_errors
def chat_pull_all(search_path, max_depth, continue_on_error, dry_run, backup_existing, force):
    """Pull chats for all discovered ClaudeSync projects."""
    
    # Build search paths
    search_paths = list(search_path) if search_path else get_default_search_paths()
    
    click.echo("💬 Starting workspace chat pull...")
    click.echo(f"🔍 Searching in {len(search_paths)} directories...")
    
    # Discover projects
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, max_depth)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        click.echo("💡 Run 'claudesync workspace discover' to see available projects")
        return
    
    click.echo(f"📋 Found {len(projects)} projects")
    # Add safety warnings if not in dry-run mode
    if not dry_run and not force:
        click.echo("\n⚠️  About to pull chats for all projects:")
        click.echo(f"  📁 {len(projects)} projects will be processed")
        click.echo(f"  💾 Existing chat files may be overwritten")
        
        if backup_existing:
            click.echo(f"  ✅ Backups will be created for existing files")
        else:
            click.echo(f"  ⚠️  No backups will be created (use --backup-existing)")
            
        if not click.confirm("\nProceed with chat pull for all projects?"):
            click.echo("❌ Workspace chat pull cancelled")
            return
    
    # Show dry-run notice
    if dry_run:
        click.echo("\n🔍 DRY RUN MODE - No files will be changed")
    
    click.echo("")
    
    # Pull chats for all projects  
    results = manager.chat_pull_all_projects(projects, dry_run, backup_existing, force)
    
    # Report results
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    click.echo("")
    click.echo("📊 Chat Pull Summary:")
    click.echo(f"  ✅ Successful: {successful}")
    click.echo(f"  ❌ Failed: {failed}")
    click.echo(f"  📋 Total: {len(results)}")
    
    if failed > 0:
        click.echo("\n❌ Failed projects:")
        for name, success in results.items():
            if not success:
                click.echo(f"  • {name}")
        
        if not continue_on_error:
            exit(1)


@workspace.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@handle_errors
def set_root(path):
    """Set the workspace root directory where all projects live."""
    
    config = WorkspaceConfig()
    
    if config.set_workspace_root(path):
        click.echo(f"✅ Workspace root set to: {path}")
        
        # Show discovered projects
        manager = WorkspaceManager()
        projects = manager.discover_projects([path], config.get_max_search_depth())
        
        if projects:
            click.echo(f"🔍 Found {len(projects)} ClaudeSync projects:")
            for project in projects[:5]:  # Show first 5
                click.echo(f"  📋 {project.name}")
            if len(projects) > 5:
                click.echo(f"  ... and {len(projects) - 5} more")
        else:
            click.echo("💡 No ClaudeSync projects found in this workspace.")
            click.echo("   Create projects with: claudesync project create")
    else:
        click.echo(f"❌ Directory does not exist: {path}")


@workspace.command()
@handle_errors  
def config():
    """Show current workspace configuration."""
    
    config = WorkspaceConfig()
    summary = config.get_config_summary()
    
    click.echo("🏢 Workspace Configuration")
    click.echo("")
    
    # Workspace root
    if summary['workspace_root']:
        status = "✅" if summary['workspace_exists'] else "❌"
        click.echo(f"📁 Workspace Root: {status} {summary['workspace_root']}")
    else:
        click.echo("📁 Workspace Root: ❌ Not configured")
        click.echo("   💡 Set with: claudesync workspace set-root /path/to/workspace")
    
    click.echo("")
    click.echo(f"🔍 Auto-discovery: {'✅ Enabled' if summary['auto_discover'] else '❌ Disabled'}")
    click.echo(f"📏 Max search depth: {summary['max_search_depth']}")
    
    # Search paths
    click.echo("")
    click.echo("🔍 Current search paths:")
    for path in summary['search_paths']:
        exists = "✅" if Path(path).exists() else "❌"
        click.echo(f"  {exists} {path}")
    
    # Exclude patterns
    if summary['exclude_patterns']:
        click.echo("")
        click.echo("🚫 Exclude patterns:")
        for pattern in summary['exclude_patterns']:
            click.echo(f"  • {pattern}")


@workspace.command()
@handle_errors
def reset():
    """Reset workspace configuration to defaults."""
    
    if click.confirm("Are you sure you want to reset workspace configuration to defaults?"):
        config = WorkspaceConfig()
        config.config = config._get_default_config()
        config._save_config()
        click.echo("✅ Workspace configuration reset to defaults")
        click.echo("💡 Use 'claudesync workspace set-root' to configure a workspace directory")


@workspace.command()
@handle_errors
def status():
    """Show workspace status and discovered projects."""
    
    # Get default search paths
    search_paths = get_default_search_paths()
    
    click.echo("🏢 Workspace Status")
    click.echo("")
    click.echo("🔍 Default search paths:")
    for path in search_paths:
        exists = "✅" if Path(path).exists() else "❌"
        click.echo(f"  {exists} {path}")
    
    click.echo("")
    click.echo("💡 Available commands:")
    click.echo("  claudesync workspace discover       # Find all projects")
    click.echo("  claudesync workspace sync-all       # Sync all projects")  
    click.echo("  claudesync workspace chat-pull-all  # Pull chats for all projects")
    click.echo("")
    click.echo("🎯 Quick start:")
    click.echo("  claudesync workspace discover       # See what projects exist")
    click.echo("  claudesync workspace sync-all       # Replace your bash script!")
