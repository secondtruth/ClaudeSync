import os
import time
import subprocess
import signal
import logging
from pathlib import Path
from datetime import datetime
from typing import Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)

class ClaudeSyncFileHandler(FileSystemEventHandler):
    """Handles file system events and triggers sync."""
    
    def __init__(self, project_path: str, config, debounce_delay: float = 2.0):
        self.project_path = project_path
        self.config = config
        self.debounce_delay = debounce_delay
        self.pending_sync = False
        self.last_sync_time = 0
        self.modified_files: Set[str] = set()
        
        # Patterns to ignore
        self.ignore_patterns = {
            '.git', '__pycache__', '.pytest_cache', 'node_modules',
            '.claudesync', 'venv', '.env', '*.pyc', '*.pyo',
            '*.swp', '*.swo', '*~', '.DS_Store'
        }
    
    def should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_obj = Path(path)
        
        # Check each part of the path
        for part in path_obj.parts:
            for pattern in self.ignore_patterns:
                if pattern.startswith('*'):
                    if part.endswith(pattern[1:]):
                        return True
                elif part == pattern:
                    return True
        
        return False
    
    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event."""
        if event.is_directory:
            return
        
        if self.should_ignore(event.src_path):
            return
        
        # Track modified file
        rel_path = os.path.relpath(event.src_path, self.project_path)
        self.modified_files.add(rel_path)
        
        # Set pending sync flag
        self.pending_sync = True
        logger.debug(f"File event: {event.event_type} - {rel_path}")
    
    def check_and_sync(self):
        """Check if sync is needed and perform it."""
        current_time = time.time()
        
        if (self.pending_sync and 
            current_time - self.last_sync_time > self.debounce_delay):
            
            logger.info(f"Syncing {len(self.modified_files)} modified files...")
            
            try:
                # Run claudesync push
                result = subprocess.run(
                    ['claudesync', 'push'],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info("Sync completed successfully")
                    self.modified_files.clear()
                else:
                    logger.error(f"Sync failed: {result.stderr}")
                    
            except Exception as e:
                logger.error(f"Error during sync: {e}")
            
            self.pending_sync = False
            self.last_sync_time = current_time

class FileWatcherService:
    """Main file watching service."""
    
    def __init__(self, config):
        self.config = config
        self.observer = None
        self.handler = None
        self.running = False
        
    def start(self, project_path: str, daemon: bool = False):
        """Start watching for file changes."""
        if daemon:
            self._start_daemon(project_path)
        else:
            self._start_foreground(project_path)
    
    def _start_foreground(self, project_path: str):
        """Start watching in foreground."""
        logger.info(f"Starting file watcher for: {project_path}")
        
        # Create handler and observer
        self.handler = ClaudeSyncFileHandler(project_path, self.config)
        self.observer = Observer()
        self.observer.schedule(self.handler, project_path, recursive=True)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start observer
        self.observer.start()
        self.running = True
        
        logger.info("File watcher started. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                self.handler.check_and_sync()
                time.sleep(0.5)
        finally:
            self.stop()
    
    def _start_daemon(self, project_path: str):
        """Start watching as daemon process."""
        import daemon
        import lockfile
        
        pid_file = os.path.join(project_path, '.claudesync', 'watch.pid')
        
        # Ensure .claudesync directory exists
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        
        # Check if already running
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)
                logger.error(f"Daemon already running with PID {pid}")
                return
            except OSError:
                # Process not running, remove stale PID file
                os.remove(pid_file)
        
        # Create daemon context
        context = daemon.DaemonContext(
            working_directory=project_path,
            pidfile=lockfile.FileLock(pid_file),
            stdout=open(os.path.join(project_path, '.claudesync', 'watch.log'), 'a'),
            stderr=open(os.path.join(project_path, '.claudesync', 'watch.log'), 'a'),
        )
        
        with context:
            # Write PID
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Start watching
            self._start_foreground(project_path)
    
    def stop(self):
        """Stop the file watcher."""
        self.running = False
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("File watcher stopped.")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, stopping...")
        self.stop()
    
    @staticmethod
    def stop_daemon(project_path: str) -> bool:
        """Stop a running daemon."""
        pid_file = os.path.join(project_path, '.claudesync', 'watch.pid')
        
        if not os.path.exists(pid_file):
            return False
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Send termination signal
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(10):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except OSError:
                    # Process terminated
                    break
            
            # Remove PID file
            os.remove(pid_file)
            return True
            
        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return False
    
    @staticmethod
    def get_daemon_status(project_path: str) -> Optional[dict]:
        """Get status of daemon if running."""
        pid_file = os.path.join(project_path, '.claudesync', 'watch.pid')
        
        if not os.path.exists(pid_file):
            return None
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is running
            os.kill(pid, 0)
            
            # Get process info
            return {
                'pid': pid,
                'status': 'running',
                'pid_file': pid_file
            }
            
        except OSError:
            # Process not running
            return {
                'pid': pid,
                'status': 'stale',
                'pid_file': pid_file
            }
        except Exception:
            return None