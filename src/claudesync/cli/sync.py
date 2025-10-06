import click
from ..syncmanager import SyncManager, SyncDirection
from ..utils import handle_errors, validate_and_get_provider, get_local_files
from ..conflict_resolver import ConflictResolver

def _print_plan(plan):
    """Print sync plan in human-readable format."""
    if plan.actions:
        click.echo("\n📋 Planned Actions:")
        for item in plan.actions:
            icon = {
                "upload": "⬆️ ",
                "download": "⬇️ ",
                "delete_local": "🗑️ ",
                "delete_remote": "🗑️ ",
                "noop": "⏭️ "
            }.get(item.action, "❓")
            click.echo(f"  {icon} {item.action.upper()}: {item.path}")
            click.echo(f"      Reason: {item.reason}")
    
    if plan.conflicts:
        click.echo("\n⚠️  Conflicts:")
        for conflict in plan.conflicts:
            click.echo(f"  ⚔️  {conflict.path}")
            click.echo(f"      {conflict.reason}")
            
    click.echo(f"\nTotal operations: {plan.total_operations}")

@click.command()
@click.option("--conflict-strategy", 
              type=click.Choice(['prompt', 'local-wins', 'remote-wins']), 
              default='prompt',
              help="How to handle conflicts during sync")
@click.option("--dry-run", is_flag=True, help="Preview changes without syncing")
@click.option("--no-pull", is_flag=True, help="Skip pulling remote changes (upload only)")
@click.option("--no-push", is_flag=True, help="Skip pushing local changes (download only)")
@click.option("--category", default=None, help="Specify the file category to sync")
@click.option("--uberproject", is_flag=True, default=False, help="Include submodules in parent project sync")
@click.pass_obj
@handle_errors
def sync(config, conflict_strategy, dry_run, no_pull, no_push, category, uberproject):
    """Synchronize local and remote files (bi-directional sync)."""
    # Determine sync direction
    if no_pull and no_push:
        click.echo("Error: Cannot use both --no-pull and --no-push")
        return
    
    direction = (
        SyncDirection.PUSH if no_pull and not no_push else
        SyncDirection.PULL if no_push and not no_pull else
        SyncDirection.BOTH
    )
    
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    active_project_name = config.get("active_project_name")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("No .claudesync directory found. Run 'csync project create' first.")
        return
    
    click.echo(f"Syncing project '{active_project_name}' ({direction.value})...")
    if category:
        click.echo(f"Using category: {category}")
    if uberproject:
        click.echo("Including submodules in sync")
    
    # Get files
    local_files = get_local_files(config, local_path, category=category, include_submodules=uberproject)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    # Initialize sync manager
    sync_manager = SyncManager(provider, config, local_path)
    
    # Build sync plan
    plan = sync_manager.build_plan(
        direction=direction,
        dry_run=dry_run,
        conflict_strategy=conflict_strategy,
        local_files=local_files,
        remote_files=remote_files
    )
    
    # Handle dry run
    if dry_run:
        _print_plan(plan)
        return
    
    # Handle conflicts with prompt strategy
    if plan.conflicts and conflict_strategy == 'prompt':
        click.echo(f"\n⚠️  {len(plan.conflicts)} conflict(s) detected!")
        _print_plan(plan)
        if not click.confirm("Continue sync anyway?"):
            raise click.Abort()
    
    # Execute plan
    if plan.total_operations > 0:
        results = sync_manager.execute_plan(plan, direction=direction)
        
        # Print results
        click.echo("\n✅ Sync Complete:")
        if results["uploaded"]:
            click.echo(f"  ⬆️  Uploaded: {results['uploaded']} files")
        if results["downloaded"]:
            click.echo(f"  ⬇️  Downloaded: {results['downloaded']} files")
        if results["deleted"]:
            click.echo(f"  🗑️  Deleted: {results['deleted']} files")
        
        if results["errors"]:
            click.echo(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results["errors"][:5]:  # Show first 5 errors
                click.echo(f"  - {error}")
    else:
        click.echo("✅ Everything is up to date!")
        
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
