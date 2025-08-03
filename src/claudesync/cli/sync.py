import click
from ..syncmanager import SyncManager
from ..utils import handle_errors, validate_and_get_provider, get_local_files
from ..conflict_resolver import ConflictResolver

@click.command()
@click.option("--conflict-strategy", 
              type=click.Choice(['prompt', 'local-wins', 'remote-wins']), 
              default='prompt',
              help="How to handle conflicts during sync")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
@click.option("--no-pull", is_flag=True, help="Skip pulling remote changes (upload only)")
@click.option("--no-push", is_flag=True, help="Skip pushing local changes (download only)")
@click.pass_obj
@handle_errors
def sync(config, conflict_strategy, dry_run, no_pull, no_push):
    """Synchronize local and remote files (bi-directional sync)."""
    provider = validate_and_get_provider(config, require_project=True)
    
    if no_pull and no_push:
        click.echo("Error: Cannot use both --no-pull and --no-push")
        return
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    active_project_name = config.get("active_project_name")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("No .claudesync directory found. Run 'csync project create' first.")
        return
    
    click.echo(f"Syncing project '{active_project_name}'...")
    
    # Get files
    local_files = get_local_files(config, local_path)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    if dry_run:
        click.echo("\nDry run - changes that would be made:")
        
        # Show files to upload
        if not no_push:
            remote_file_names = {f['file_name'] for f in remote_files}
            files_to_upload = [f for f in local_files if f not in remote_file_names]
            if files_to_upload:
                click.echo("\nFiles to upload:")
                for f in files_to_upload:
                    click.echo(f"  [UPLOAD] {f}")
        
        # Show files to download
        if not no_pull:
            files_to_download = []
            for remote_file in remote_files:
                if remote_file['file_name'] not in local_files:
                    files_to_download.append(remote_file['file_name'])
            if files_to_download:
                click.echo("\nFiles to download:")
                for f in files_to_download:
                    click.echo(f"  [DOWNLOAD] {f}")
        
        # Show conflicts
        resolver = ConflictResolver(config)
        conflicts = resolver.detect_conflicts(local_files, remote_files)
        if conflicts:
            click.echo(f"\nConflicts detected ({len(conflicts)} files):")
            for c in conflicts:
                click.echo(f"  [CONFLICT] {c['file_name']}")
        
        return
    
    # Handle conflicts
    resolver = ConflictResolver(config)
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    if conflicts and not no_pull:
        click.echo(f"\n⚠️  {len(conflicts)} conflict(s) detected!")
        
        for conflict in conflicts:
            resolved = resolver.resolve_conflict(conflict, strategy=conflict_strategy)
            if resolved:
                with open(conflict['local_path'], 'w', encoding='utf-8') as f:
                    f.write(resolved)
                click.echo(f"  ✓ Resolved: {conflict['file_name']}")
    
    # Create sync manager
    sync_manager = SyncManager(provider, config, local_path)
    
    # Perform sync based on options
    if no_pull:
        # Push only (like old push command)
        config.set("two_way_sync", False, local=True)
        sync_manager.sync(local_files, remote_files)
        click.echo("✓ Push complete")
    elif no_push:
        # Pull only
        config.set("two_way_sync", True, local=True)
        # Temporarily clear local files to force download
        sync_manager.sync({}, remote_files)
        click.echo("✓ Pull complete")
    else:
        # Full bi-directional sync
        config.set("two_way_sync", True, local=True)
        sync_manager.sync(local_files, remote_files)
        click.echo("✓ Sync complete")
    
    click.echo(f"Project URL: https://claude.ai/project/{active_project_id}")

# Keep the existing schedule command
@click.command()
@click.pass_obj
@click.option(
    "--interval", type=int, default=5, prompt="Enter sync interval in minutes"
)
@handle_errors
def schedule(config, interval):
    """Set up automated synchronization using system scheduler."""
    import platform
    import os
    import subprocess
    
    system = platform.system()
    
    if system == "Windows":
        # Windows Task Scheduler
        task_name = "ClaudeSync_AutoSync"
        csync_path = shutil.which("csync")
        
        if not csync_path:
            click.echo("Error: csync command not found in PATH")
            return
        
        # Create scheduled task
        cmd = f'schtasks /create /tn "{task_name}" /tr "{csync_path} sync" /sc minute /mo {interval} /f'
        
        try:
            subprocess.run(cmd, shell=True, check=True)
            click.echo(f"✓ Scheduled sync every {interval} minutes on Windows")
            click.echo(f"  Task name: {task_name}")
            click.echo(f"  To remove: schtasks /delete /tn \"{task_name}\" /f")
        except subprocess.CalledProcessError:
            click.echo("Error creating scheduled task")
    
    elif system == "Linux" or system == "Darwin":
        # Unix-like systems (cron)
        import tempfile
        
        # Get current crontab
        try:
            current_cron = subprocess.check_output(['crontab', '-l'], text=True)
        except subprocess.CalledProcessError:
            current_cron = ""
        
        # Add new cron job
        csync_path = shutil.which("csync")
        if not csync_path:
            click.echo("Error: csync command not found in PATH")
            return
        
        new_job = f"*/{interval} * * * * cd {os.getcwd()} && {csync_path} sync\n"
        
        # Check if job already exists
        if new_job.strip() in current_cron:
            click.echo("Sync schedule already exists")
            return
        
        # Write new crontab
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(current_cron)
            f.write(new_job)
            temp_file = f.name
        
        try:
            subprocess.run(['crontab', temp_file], check=True)
            os.unlink(temp_file)
            click.echo(f"✓ Scheduled sync every {interval} minutes using cron")
            click.echo(f"  To view: crontab -l")
            click.echo(f"  To remove: crontab -e (and delete the ClaudeSync line)")
        except subprocess.CalledProcessError:
            click.echo("Error setting up cron job")
            os.unlink(temp_file)
    
    else:
        click.echo(f"Automated scheduling not supported on {system}")
