#!/usr/bin/env python3
"""
ClaudeSync System Tray GUI - Background sync with taskbar integration.
"""
import sys
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

try:
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget
    from PyQt6.QtCore import QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QIcon, QAction
except ImportError:
    print("PyQt6 not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt6"])
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QWidget
    from PyQt6.QtCore import QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QIcon, QAction

# Import our sync module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from claudesync.workspace_sync import WorkspaceSync
from claudesync.provider_factory import get_provider
from claudesync.configmanager import FileConfigManager


class SyncWorker(QThread):
    """Background thread for sync operations."""
    status_update = pyqtSignal(str)
    sync_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, workspace_root, provider, bidirectional=False, sync_chats=False):
        super().__init__()
        self.workspace_root = workspace_root
        self.provider = provider
        self.bidirectional = bidirectional
        self.sync_chats = sync_chats
        self.syncer = WorkspaceSync(workspace_root, provider)

    def run(self):
        """Run sync in background thread."""
        try:
            self.status_update.emit("Syncing workspace...")
            stats = self.syncer.sync_all(
                dry_run=False,
                bidirectional=self.bidirectional,
                sync_chats=self.sync_chats,
                conflict_strategy="remote"
            )
            self.sync_complete.emit(stats)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ClaudeSyncTray(QSystemTrayIcon):
    """System tray application for ClaudeSync."""

    def __init__(self):
        super().__init__()

        # Load configuration
        self.config = FileConfigManager()
        self.workspace_config_file = Path.home() / ".claudesync" / "workspace.json"
        self.load_workspace_config()

        # Setup provider
        self.provider = None
        self.authenticate()

        # Setup UI
        self.setup_ui()

        # Auto-sync timer
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self.auto_sync)
        self.last_sync = None
        self.sync_interval = 30  # minutes
        self.enable_auto_sync(True)

        # Current sync worker
        self.sync_worker = None

    def load_workspace_config(self):
        """Load workspace configuration."""
        if self.workspace_config_file.exists():
            with open(self.workspace_config_file, 'r', encoding='utf-8') as f:
                self.workspace_config = json.load(f)
                self.workspace_root = Path(self.workspace_config.get("workspace_root", "."))
        else:
            self.workspace_config = {}
            self.workspace_root = None

    def authenticate(self):
        """Authenticate with Claude.ai."""
        try:
            session_key, _ = self.config.get_session_key("claude.ai")
            if session_key:
                self.provider = get_provider(self.config, "claude.ai")
                return True
        except Exception:
            pass
        return False

    def setup_ui(self):
        """Setup system tray UI."""
        # Create tray icon
        icon_path = Path(__file__).parent / "icon.png"
        if not icon_path.exists():
            # Create simple icon if doesn't exist
            self.create_default_icon(icon_path)

        self.setIcon(QIcon(str(icon_path)))
        self.setToolTip("ClaudeSync - Workspace Sync")

        # Create menu
        menu = QMenu()

        # Status
        self.status_action = QAction("Status: Ready", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)
        menu.addSeparator()

        # Sync now
        self.sync_action = QAction("Sync Now", menu)
        self.sync_action.triggered.connect(self.manual_sync)
        menu.addAction(self.sync_action)

        # Bidirectional sync
        self.bi_sync_action = QAction("Bidirectional Sync", menu)
        self.bi_sync_action.triggered.connect(lambda: self.manual_sync(bidirectional=True))
        menu.addAction(self.bi_sync_action)

        # Sync with chats
        self.chat_sync_action = QAction("Sync with Chats", menu)
        self.chat_sync_action.triggered.connect(lambda: self.manual_sync(sync_chats=True))
        menu.addAction(self.chat_sync_action)

        menu.addSeparator()

        # Auto-sync toggle
        self.auto_sync_action = QAction("Auto-sync (30 min)", menu)
        self.auto_sync_action.setCheckable(True)
        self.auto_sync_action.setChecked(True)
        self.auto_sync_action.triggered.connect(self.toggle_auto_sync)
        menu.addAction(self.auto_sync_action)

        menu.addSeparator()

        # Last sync info
        self.last_sync_action = QAction("Last sync: Never", menu)
        self.last_sync_action.setEnabled(False)
        menu.addAction(self.last_sync_action)

        menu.addSeparator()

        # Exit
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)

        self.setContextMenu(menu)
        self.show()

    def create_default_icon(self, path):
        """Create a simple default icon."""
        from PyQt6.QtGui import QPixmap, QPainter, QBrush
        from PyQt6.QtCore import Qt

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setBrush(QBrush(Qt.GlobalColor.blue))
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()

        pixmap.save(str(path))

    def manual_sync(self, bidirectional=False, sync_chats=False):
        """Manually trigger sync."""
        if not self.workspace_root:
            self.show_message("Error", "No workspace configured")
            return

        if not self.provider:
            if not self.authenticate():
                self.show_message("Error", "Not authenticated")
                return

        if self.sync_worker and self.sync_worker.isRunning():
            self.show_message("Info", "Sync already in progress")
            return

        # Start sync
        self.sync_worker = SyncWorker(
            self.workspace_root,
            self.provider,
            bidirectional,
            sync_chats
        )
        self.sync_worker.status_update.connect(self.update_status)
        self.sync_worker.sync_complete.connect(self.on_sync_complete)
        self.sync_worker.error_occurred.connect(self.on_sync_error)
        self.sync_worker.start()

        self.sync_action.setEnabled(False)
        self.bi_sync_action.setEnabled(False)
        self.chat_sync_action.setEnabled(False)

    def auto_sync(self):
        """Auto-sync callback."""
        if datetime.now() - self.last_sync > timedelta(minutes=self.sync_interval):
            self.manual_sync()

    def toggle_auto_sync(self):
        """Toggle auto-sync on/off."""
        self.enable_auto_sync(self.auto_sync_action.isChecked())

    def enable_auto_sync(self, enabled):
        """Enable or disable auto-sync."""
        if enabled:
            self.sync_timer.start(60000)  # Check every minute
            if not self.last_sync:
                self.last_sync = datetime.now()
        else:
            self.sync_timer.stop()

    def update_status(self, status):
        """Update status in menu."""
        self.status_action.setText(f"Status: {status}")
        self.setToolTip(f"ClaudeSync - {status}")

    def on_sync_complete(self, stats):
        """Handle sync completion."""
        self.last_sync = datetime.now()
        self.last_sync_action.setText(f"Last sync: {self.last_sync.strftime('%H:%M')}")

        # Build summary
        summary = f"Synced {stats['created']} new, {stats['updated']} updated"
        if stats.get('uploaded'):
            summary += f", {stats['uploaded']} uploaded"
        if stats.get('chats'):
            summary += f", {stats['chats']} chats"

        self.update_status("Ready")
        self.show_message("Sync Complete", summary)

        # Re-enable sync actions
        self.sync_action.setEnabled(True)
        self.bi_sync_action.setEnabled(True)
        self.chat_sync_action.setEnabled(True)

    def on_sync_error(self, error):
        """Handle sync error."""
        self.update_status("Error")
        self.show_message("Sync Error", error)

        # Re-enable sync actions
        self.sync_action.setEnabled(True)
        self.bi_sync_action.setEnabled(True)
        self.chat_sync_action.setEnabled(True)

    def show_message(self, title, message):
        """Show system notification."""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def quit_app(self):
        """Quit application."""
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.terminate()
        QApplication.quit()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Check if system tray is available
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Error", "System tray not available")
        sys.exit(1)

    # Create and show tray
    tray = ClaudeSyncTray()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()