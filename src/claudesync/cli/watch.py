import click
import subprocess
import time
import os
from ..utils import handle_errors
from ..file_watcher import FileWatcherService

@click.group()
def watch():
    """Watch for file changes and auto-sync."""
    pass

@watch.command()
@click.option('--daemon', '-d', is_flag=True, help='Run as background daemon')
@click.option('--startup-sync', is_flag=True, help='Perform initial sync on startup')
@click.pass_obj
@handle_errors
def start(config, daemon, startup_sync):
    """Start watching for file changes."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured. Run 'claudesync project create' or 'claudesync project set' first.")
        return
    
    # Perform startup sync if requested
    if startup_sync:
        click.echo("Performing initial sync...")
        result = subprocess.run(['csync', 'push'], cwd=local_path)
        if result.returncode != 0:
            click.echo("Initial sync failed. Aborting.")
            return
    
    # Create watcher service
    watcher = FileWatcherService(config)
    
    if daemon:
        click.echo(f"Starting file watcher daemon for: {local_path}")
        watcher.start(local_path, daemon=True)
        click.echo("Daemon started. Use 'claudesync watch status' to check status.")
        click.echo("Use 'claudesync watch stop' to stop the daemon.")
    else:
        click.echo(f"Starting file watcher for: {local_path}")
        click.echo("Press Ctrl+C to stop watching.")
        watcher.start(local_path, daemon=False)

@watch.command()
@click.pass_obj
@handle_errors  
def stop(config):
    """Stop the file watcher daemon."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    if FileWatcherService.stop_daemon(local_path):
        click.echo("File watcher daemon stopped.")
    else:
        click.echo("No daemon found or already stopped.")

@watch.command()
@click.pass_obj
@handle_errors
def status(config):
    """Check file watcher daemon status."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    status = FileWatcherService.get_daemon_status(local_path)
    
    if not status:
        click.echo("File watcher daemon is not running.")
    elif status['status'] == 'running':
        click.echo(f"File watcher daemon is running (PID: {status['pid']})")
        
        # Check log file
        log_file = os.path.join(local_path, '.claudesync', 'watch.log')
        if os.path.exists(log_file):
            # Show last few lines of log
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent = lines[-10:] if len(lines) > 10 else lines
                
                if recent:
                    click.echo("\nRecent activity:")
                    for line in recent:
                        click.echo(f"  {line.strip()}")
    else:
        click.echo(f"Stale PID file found (PID: {status['pid']})")
        click.echo("Run 'claudesync watch stop' to clean up.")

@watch.command()
@click.pass_obj
@handle_errors
def sync_now(config):
    """Trigger immediate sync (useful when daemon is running)."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    click.echo("Triggering sync...")
    result = subprocess.run(['csync', 'push'], cwd=local_path)
    
    if result.returncode == 0:
        click.echo("Sync completed successfully.")
    else:
        click.echo("Sync failed. Check the logs for details.")