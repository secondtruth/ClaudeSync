"""
Simple file watching service for ClaudeSync.
Conservative implementation that doesn't modify existing functionality.
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class ClaudeSyncFileHandler(FileSystemEventHandler):
    """Handles file system events for ClaudeSync."""
    
    def __init__(self, sync_callback: Callable = None, debounce_seconds: float = 2.0):
        """
        Initialize the file handler.
        
        Args:
            sync_callback: Function to call when sync is needed
            debounce_seconds: Seconds to wait before triggering sync
        """
        self.sync_callback = sync_callback
        self.debounce_seconds = debounce_seconds
        self.last_event_time = 0
        self.timer = None
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        # Only watch files that claudesync would normally sync
        if self._should_sync_file(event.src_path):
            self._debounced_sync()
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._should_sync_file(event.src_path):
            self._debounced_sync()
    
    def on_deleted(self, event):
        """Handle file deletion events."""
        if not event.is_directory:
            self._debounced_sync()
    
    def _should_sync_file(self, file_path: str) -> bool:
        """Check if a file should trigger a sync."""
        path = Path(file_path)
        
        # Skip hidden files and temporary files
        if path.name.startswith('.') or path.name.endswith('~'):
            return False
            
        # Skip common temporary/build directories
        excluded_dirs = {'.git', '__pycache__', 'node_modules', '.vscode', '.idea'}
        if any(excluded_dir in path.parts for excluded_dir in excluded_dirs):
            return False
            
        return True
    
    def _debounced_sync(self):
        """Trigger sync with debouncing to avoid excessive syncing."""
        current_time = time.time()
        self.last_event_time = current_time
        
        # Cancel existing timer
        if self.timer:
            self.timer.cancel()
        
        # Start new timer
        self.timer = threading.Timer(self.debounce_seconds, self._execute_sync)
        self.timer.start()
    
    def _execute_sync(self):
        """Execute the sync callback if still needed."""
        if self.sync_callback:
            try:
                logger.info("File changes detected, triggering sync...")
                self.sync_callback()
            except Exception as e:
                logger.error(f"Error during file watching sync: {e}")


class FileWatcherService:
    """Service for watching file changes and triggering syncs."""
    
    def __init__(self, watch_path: str, sync_callback: Callable = None):
        """
        Initialize the file watcher service.
        
        Args:
            watch_path: Directory to watch for changes
            sync_callback: Function to call when sync is needed
        """
        self.watch_path = Path(watch_path)
        self.sync_callback = sync_callback
        self.observer = None
        self.is_running = False
        
    def start(self) -> bool:
        """
        Start watching for file changes.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("File watcher is already running")
            return False
            
        if not self.watch_path.exists():
            logger.error(f"Watch path does not exist: {self.watch_path}")
            return False
            
        try:
            # Create event handler
            event_handler = ClaudeSyncFileHandler(
                sync_callback=self.sync_callback,
                debounce_seconds=2.0
            )
            
            # Create and start observer
            self.observer = Observer()
            self.observer.schedule(
                event_handler,
                str(self.watch_path),
                recursive=True
            )
            self.observer.start()
            self.is_running = True
            
            logger.info(f"Started watching {self.watch_path} for file changes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return False
    
    def stop(self):
        """Stop watching for file changes."""
        if not self.is_running:
            return
            
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            
        self.is_running = False
        logger.info("Stopped file watching")
    
    def is_watching(self) -> bool:
        """Check if the service is currently watching."""
        return self.is_running and self.observer and self.observer.is_alive()
