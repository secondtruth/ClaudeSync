import click
import os
from ..syncmanager import SyncManager
from ..utils import handle_errors, validate_and_get_provider, get_local_files
from ..conflict_resolver import ConflictResolver

@click.command()
@click.option("-l", "--local-path", default=".", help="The local directory to pull to.")
@click.option("--dry-run", is_flag=True, help="Show what would be pulled without making changes.")
@click.option("--force", is_flag=True, help="Force pull, overwriting local changes.")
@click.option("--merge", is_flag=True, help="Merge remote changes with local (detect conflicts).")
@click.pass_obj
@handle_errors
def pull(config, local_path, dry_run, force, merge):
    """Pull files from Claude project to local directory (download only)."""
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    active_project_name = config.get("active_project_name")
    
    # Get the local path
    if local_path == ".":
        local_path = config.get_local_path()
        if not local_path:
            click.echo(
                "No .claudesync directory found. "
                "Please run 'csync project create' or 'csync project set' first."
            )
            return
    
    click.echo(f"Pulling from project '{active_project_name}'...")
    
    # Get remote files
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    if dry_run:
        click.echo("\nDry run - would pull the following files:")
        for remote_file in remote_files:
            file_name = remote_file['file_name']
            local_file_path = os.path.join(local_path, file_name)
            if os.path.exists(local_file_path):
                click.echo(f"  [UPDATE] {file_name}")
            else:
                click.echo(f"  [NEW]    {file_name}")
        return
    
    # Handle conflicts if merge mode
    if merge and not force:
        local_files = get_local_files(config, local_path)
        resolver = ConflictResolver(config)
        conflicts = resolver.detect_conflicts(local_files, remote_files)
        
        if conflicts:
            click.echo(f"\n⚠️  {len(conflicts)} conflict(s) detected!")
            for conflict in conflicts:
                click.echo(f"  - {conflict['file_name']}")
            
            if not click.confirm("\nResolve conflicts interactively?"):
                click.echo("Pull cancelled. Use --force to overwrite local changes.")
                return
            
            # Resolve each conflict
            for conflict in conflicts:
                resolved = resolver.resolve_conflict(conflict, strategy='prompt')
                if resolved:
                    with open(conflict['local_path'], 'w', encoding='utf-8') as f:
                        f.write(resolved)
    
    # Create a temporary sync manager for pull operations
    sync_manager = SyncManager(provider, config, local_path)
    
    # Temporarily enable two-way sync for pull
    original_two_way = config.get("two_way_sync", False)
    config.set("two_way_sync", True, local=True)
    
    # Pull files (only remote to local)
    pulled_files = 0
    updated_files = 0
    
    try:
        for remote_file in remote_files:
            file_name = remote_file['file_name']
            local_file_path = os.path.join(local_path, file_name)
            
            # Check if file exists locally
            exists_locally = os.path.exists(local_file_path)
            
            if exists_locally and not force and not merge:
                # Skip if file exists and not forcing
                click.echo(f"  [SKIP]   {file_name} (use --force to overwrite)")
                continue
            
            # Create directory if needed
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Write file
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(remote_file.get('content', ''))
            
            if exists_locally:
                updated_files += 1
                click.echo(f"  [UPDATE] {file_name}")
            else:
                pulled_files += 1
                click.echo(f"  [NEW]    {file_name}")
    
    finally:
        # Restore original two-way sync setting
        config.set("two_way_sync", original_two_way, local=True)
    
    click.echo(f"\n✓ Pull complete: {pulled_files} new, {updated_files} updated")
