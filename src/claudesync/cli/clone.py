import click
import os
from pathlib import Path
from ..utils import handle_errors, validate_and_get_provider
from ..syncmanager import SyncManager
from ..configmanager import FileConfigManager

@click.command()
@click.option('--workspace-root', help='Root directory for cloning projects')
@click.option('--dry-run', is_flag=True, help='Show what would be cloned without cloning')
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.option('--skip-existing', is_flag=True, help='Skip projects that already exist locally')
@click.option('--clean', is_flag=True, help='Remove empty directories before cloning')
@click.pass_obj
@handle_errors
def clone_all(config, workspace_root, dry_run, include_archived, skip_existing, clean):
    """Clone all remote Claude projects to local workspace."""
    provider = validate_and_get_provider(config)
    
    # Determine workspace root
    if not workspace_root:
        from ..workspace_config import WorkspaceConfig
        ws_config = WorkspaceConfig()
        workspace_root = ws_config.get_workspace_root()
        
        if not workspace_root:
            workspace_root = click.prompt("Enter workspace root directory", 
                                        default=os.path.expanduser("~/claude-projects"))
    
    workspace_root = os.path.expanduser(workspace_root)
    
    if not dry_run and not os.path.exists(workspace_root):
        os.makedirs(workspace_root, exist_ok=True)
    
    click.echo(f"Workspace root: {workspace_root}")
    
    # Clean empty directories if requested
    if clean and not dry_run and os.path.exists(workspace_root):
        click.echo("\nCleaning empty directories...")
        import shutil
        for item in os.listdir(workspace_root):
            item_path = os.path.join(workspace_root, item)
            if os.path.isdir(item_path):
                # Check if it's an empty directory or has no .claudesync
                claudesync_path = os.path.join(item_path, '.claudesync', 'config.local.json')
                if not os.path.exists(claudesync_path):
                    try:
                        if not os.listdir(item_path):  # Empty directory
                            os.rmdir(item_path)
                            click.echo(f"  Removed empty: {item}")
                    except:
                        pass
    
    # Get organization
    org_id = config.get('active_organization_id')
    if not org_id:
        click.echo("No active organization. Run 'csync auth login' first.")
        return
    
    # List all projects
    click.echo("\nFetching remote projects...")
    projects = provider.get_projects(org_id, include_archived=include_archived)
    
    if not projects:
        click.echo("No projects found.")
        return
    
    click.echo(f"Found {len(projects)} project(s)")
    
    # Process each project
    cloned = 0
    skipped = 0
    failed = 0
    
    for project in projects:
        project_name = project['name']
        project_id = project['id']
        is_archived = project.get('archived_at') is not None
        
        # Sanitize project name for filesystem (keep emojis)
        import unicodedata
        # Only replace truly problematic characters for filesystems
        invalid_chars = '<>:"/\\|?*'
        safe_name = "".join(c if c not in invalid_chars else '_' 
                           for c in project_name).strip()
        # Remove any trailing dots or spaces (Windows compatibility)
        safe_name = safe_name.rstrip('. ')
        project_path = os.path.join(workspace_root, safe_name)
        
        # Check if already exists
        claudesync_config = os.path.join(project_path, '.claudesync', 'config.local.json')
        
        if os.path.exists(project_path) and os.path.exists(claudesync_config):
            # This is a valid ClaudeSync project
            if skip_existing:
                click.echo(f"[SKIP] {project_name} - already exists")
                skipped += 1
                continue
        
        if dry_run:
            status = "[ARCHIVED]" if is_archived else "[ACTIVE]"
            click.echo(f"[DRY RUN] Would clone {status} {project_name} -> {project_path}")
            continue
        
        # Create project directory
        try:
            click.echo(f"\nCloning: {project_name}")
            os.makedirs(project_path, exist_ok=True)
            
            # Change to project directory to ensure config is created correctly
            original_cwd = os.getcwd()
            os.chdir(project_path)
            
            # Create local config manager - it will create .claudesync directory
            local_config = FileConfigManager()
            
            # Force it to recognize this as the local path
            local_config.set('local_path', project_path, local=True)
            
            # Set other configuration values
            local_config.set('active_provider', config.get('active_provider'), local=True)
            local_config.set('active_organization_id', org_id, local=True)
            local_config.set('active_project_id', project_id, local=True)
            local_config.set('active_project_name', project_name, local=True)
            local_config.set('two_way_sync', True, local=True)
            local_config.set('prune_remote_files', False, local=True)
            
            # Change back to original directory
            os.chdir(original_cwd)
            
            # Get remote files
            click.echo("  Fetching files...")
            remote_files = provider.list_files(org_id, project_id)
            
            # Download each file
            downloaded = 0
            for remote_file in remote_files:
                file_name = remote_file['file_name']
                file_path = os.path.join(project_path, file_name)
                
                # Create directories if needed
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Write file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(remote_file.get('content', ''))
                
                downloaded += 1
            
            click.echo(f"  ✓ Cloned {downloaded} files")
            cloned += 1
            
        except Exception as e:
            click.echo(f"  ✗ Failed: {str(e)}")
            failed += 1
    
    if not dry_run:
        click.echo(f"\nSummary:")
        click.echo(f"  Cloned: {cloned}")
        click.echo(f"  Skipped: {skipped}")
        click.echo(f"  Failed: {failed}")
        click.echo(f"\nWorkspace root: {workspace_root}")


@click.command()
@click.option('--format', type=click.Choice(['table', 'json', 'simple']), 
              default='table', help='Output format')
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.pass_obj
@handle_errors
def list_remote(config, format, include_archived):
    """List all remote Claude projects with details."""
    provider = validate_and_get_provider(config)
    
    org_id = config.get('active_organization_id')
    if not org_id:
        click.echo("No active organization. Run 'csync auth login' first.")
        return
    
    projects = provider.get_projects(org_id, include_archived=include_archived)
    
    if not projects:
        click.echo("No projects found.")
        return
    
    if format == 'json':
        import json
        click.echo(json.dumps(projects, indent=2))
    elif format == 'simple':
        for project in projects:
            click.echo(project['id'])
    else:  # table format
        click.echo(f"\nRemote Projects ({len(projects)} total):")
        click.echo("=" * 80)
        
        for project in projects:
            status = "[ARCHIVED]" if project.get('archived_at') else "[ACTIVE]  "
            click.echo(f"{status} {project['name']}")
            click.echo(f"         ID: {project['id']}")
            if project.get('description'):
                click.echo(f"         Description: {project['description']}")
            click.echo()
