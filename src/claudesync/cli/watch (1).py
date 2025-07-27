"""
File watching CLI commands for ClaudeSync.
Conservative implementation that adds file watching capability.
"""

import click
import subprocess
import logging
import os
import sys
import signal
import time
from pathlib import Path
from ..utils import handle_errors

logger = logging.getLogger(__name__)


@click.group()
def watch():
    """File watching commands for auto-sync."""
    pass


@watch.command()
@click.option(
    "--startup-sync", 
    is_flag=True, 
    help="Perform initial sync before starting to watch"
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Run in background as daemon process"
)
@click.pass_obj
@handle_errors
def start(config, startup_sync, daemon):
    """Start watching files for changes and auto-sync."""
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo(
            "No .claudesync directory found. "
            "Please run 'claudesync project create' or 'claudesync project set' first."
        )
        return
    
    # Check if we have required dependencies
    try:
        from ..file_watcher import FileWatcherService
    except ImportError:
        click.echo(
            "File watching requires the 'watchdog' package. "
            "Please install it with: pip install watchdog"
        )
        return
    
    click.echo(f"Starting file watcher for: {local_path}")
    
    # Handle daemon mode
    if daemon:
        click.echo("🔄 Starting daemon mode...")
        return _start_daemon(config, local_path, startup_sync)
    
    # Regular foreground mode
    return _start_foreground(config, local_path, startup_sync)


def _start_daemon(config, local_path, startup_sync):
    """Start file watcher in daemon mode."""
    try:
        # Create daemon process
        pid = os.fork()
        if pid > 0:
            # Parent process
            click.echo(f"✅ File watcher daemon started with PID: {pid}")
            click.echo("💡 Use 'claudesync watch status' to check status")
            click.echo("💡 Use 'claudesync watch stop' to stop watching")
            return
    except OSError:
        click.echo("❌ Failed to create daemon process")
        return
    
    # Child process - become daemon
    os.setsid()  # Create new session
    
    # Second fork to ensure we're not session leader
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)  # Exit second parent
    except OSError:
        sys.exit(1)
    
    # Redirect stdin, stdout, stderr to /dev/null
    sys.stdin.close()
    sys.stdout.close() 
    sys.stderr.close()
    
    # Save daemon PID for status/stop commands
    pid_file = Path(local_path) / '.claudesync' / 'watch.pid'
    pid_file.parent.mkdir(exist_ok=True)
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    # Start watching in daemon mode
    _run_file_watcher(local_path, startup_sync, daemon=True)


def _start_foreground(config, local_path, startup_sync):
    """Start file watcher in foreground mode."""
    click.echo("✅ File watcher started. Press Ctrl+C to stop...")
    _run_file_watcher(local_path, startup_sync, daemon=False)


def _run_file_watcher(local_path, startup_sync, daemon=False):
    """Run the actual file watcher logic."""
    # Check if we have required dependencies
    try:
        from ..file_watcher import FileWatcherService
    except ImportError:
        if not daemon:
            click.echo(
                "File watching requires the 'watchdog' package. "
                "Please install it with: pip install watchdog"
            )
        return
    
    # Perform startup sync if requested
    if startup_sync:
        if not daemon:
            click.echo("Performing startup sync...")
        try:
            result = subprocess.run(
                ["claudesync", "push"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            if result.returncode == 0 and not daemon:
                click.echo("✅ Startup sync completed successfully")
            elif result.returncode != 0 and not daemon:
                click.echo(f"⚠️ Startup sync had issues: {result.stderr}")
        except Exception as e:
            if not daemon:
                click.echo(f"⚠️ Startup sync failed: {e}")
    
    # Define sync callback
    def sync_callback():
        try:
            result = subprocess.run(
                ["claudesync", "push"],
                cwd=local_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            # Only show output in foreground mode
            if not daemon:
                if result.returncode == 0:
                    click.echo("✅ Auto-sync completed")
                else:
                    click.echo(f"⚠️ Auto-sync had issues: {result.stderr}")
        except Exception as e:
            if not daemon:
                click.echo(f"❌ Auto-sync failed: {e}")
    
    # Start file watcher
    watcher = FileWatcherService(local_path, sync_callback)
    
    if not watcher.start():
        if not daemon:
            click.echo("❌ Failed to start file watcher")
        return
    
    # Handle cleanup on exit
    def cleanup_handler(signum, frame):
        watcher.stop()
        # Remove PID file if in daemon mode
        if daemon:
            pid_file = Path(local_path) / '.claudesync' / 'watch.pid'
            if pid_file.exists():
                pid_file.unlink()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)
    
    try:
        # Keep the process running
        while watcher.is_watching():
            time.sleep(1)
    except KeyboardInterrupt:
        if not daemon:
            click.echo("\n🛑 Stopping file watcher...")
        watcher.stop()
        if not daemon:
            click.echo("✅ File watcher stopped")


@watch.command()
@click.pass_obj
@handle_errors
def stop(config):
    """Stop file watcher daemon."""
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No project configured")
        return
    
    pid_file = Path(local_path) / '.claudesync' / 'watch.pid'
    
    if not pid_file.exists():
        click.echo("❌ No file watcher daemon running")
        return
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Try to terminate the process
        os.kill(pid, signal.SIGTERM)
        
        # Wait a moment and check if it's gone
        time.sleep(1)
        try:
            os.kill(pid, 0)  # Check if process still exists
            click.echo("⚠️ Process may still be running")
        except OSError:
            click.echo("✅ File watcher daemon stopped")
            pid_file.unlink()
            
    except (ValueError, OSError) as e:
        click.echo(f"❌ Failed to stop daemon: {e}")
        # Clean up stale PID file
        if pid_file.exists():
            pid_file.unlink()


@watch.command()
@click.pass_obj
@handle_errors
def status(config):
    """Show file watching status and configuration."""
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No project configured")
        return
    
    click.echo(f"📁 Project path: {local_path}")
    
    # Check daemon status
    pid_file = Path(local_path) / '.claudesync' / 'watch.pid'
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)  # Check if process exists
                click.echo(f"🟢 File watcher daemon: Running (PID: {pid})")
            except OSError:
                click.echo("🔴 File watcher daemon: Stopped (stale PID file)")
                pid_file.unlink()
        except (ValueError, FileNotFoundError):
            click.echo("🔴 File watcher daemon: Stopped")
    else:
        click.echo("🔴 File watcher daemon: Stopped")
    
    click.echo(f"🔍 File watcher: Available")
    
    # Show basic configuration
    active_project_name = config.get("active_project_name")
    if active_project_name:
        click.echo(f"📋 Active project: {active_project_name}")
    
    click.echo("\n💡 Available commands:")
    click.echo("  claudesync watch start                    # Start watching (foreground)")
    click.echo("  claudesync watch start --daemon           # Start as background daemon")
    click.echo("  claudesync watch start --startup-sync     # Start with initial sync")
    click.echo("  claudesync watch stop                     # Stop daemon")
    click.echo("  claudesync watch sync-now                 # Manual sync trigger")


@watch.command()
@click.pass_obj
@handle_errors
def sync_now(config):
    """Manually trigger a sync (same as 'claudesync push')."""
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No project configured")
        return
    
    click.echo("🔄 Triggering manual sync...")
    try:
        result = subprocess.run(
            ["claudesync", "push"],
            cwd=local_path,
            timeout=300
        )
        if result.returncode == 0:
            click.echo("✅ Manual sync completed")
        else:
            click.echo("⚠️ Manual sync had issues")
    except Exception as e:
        click.echo(f"❌ Manual sync failed: {e}")
