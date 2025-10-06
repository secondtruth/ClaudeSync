"""
Project metadata manager for tracking sync operations.

This module manages the meta.json file stored in <project directory>/.claudesync/meta.json
which tracks sync history. Project pairing info is read from config.local.json instead
of being duplicated here.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages project-level metadata for sync tracking."""

    META_FILE = "meta.json"

    def __init__(self, project_root: Path, config=None):
        """
        Initialize metadata manager for a project.

        Args:
            project_root: Root directory of the project (contains .claudesync folder)
            config: Optional config manager to read project info from
        """
        self.project_root = Path(project_root)
        self.claudesync_dir = self.project_root / ".claudesync"
        self.meta_file = self.claudesync_dir / self.META_FILE
        self.config = config
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from meta.json file."""
        if not self.meta_file.exists():
            return self._get_default_metadata()

        try:
            with open(self.meta_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                # Ensure all required fields exist
                defaults = self._get_default_metadata()
                for key, value in defaults.items():
                    if key not in metadata:
                        metadata[key] = value
                return metadata
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load metadata from {self.meta_file}: {e}")
            return self._get_default_metadata()

    def _get_default_metadata(self) -> Dict[str, Any]:
        """Return default metadata structure."""
        return {
            "last_sync": None,
            "last_sync_direction": None,  # "push", "pull", "both"
            "sync_history": []  # List of sync operations with timestamps
        }

    def _save_metadata(self):
        """Save metadata to meta.json file."""
        try:
            self.claudesync_dir.mkdir(parents=True, exist_ok=True)
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save metadata to {self.meta_file}: {e}")
            raise

    def record_sync(self, direction: str, files_synced: int = 0, status: str = "success"):
        """
        Record a sync operation.

        Args:
            direction: Sync direction ("push", "pull", "both")
            files_synced: Number of files synced
            status: Sync status ("success", "failed", "partial")
        """
        now = datetime.now().isoformat()
        self._metadata["last_sync"] = now
        self._metadata["last_sync_direction"] = direction

        # Add to sync history
        sync_record = {
            "timestamp": now,
            "direction": direction,
            "files_synced": files_synced,
            "status": status
        }

        if "sync_history" not in self._metadata:
            self._metadata["sync_history"] = []

        self._metadata["sync_history"].append(sync_record)

        # Keep only last 50 sync records
        if len(self._metadata["sync_history"]) > 50:
            self._metadata["sync_history"] = self._metadata["sync_history"][-50:]

        self._save_metadata()

    def get_project_id(self) -> Optional[str]:
        """Get the paired project ID from config."""
        if self.config:
            return self.config.get("active_project_id")
        return None

    def get_project_name(self) -> Optional[str]:
        """Get the paired project name from config."""
        if self.config:
            return self.config.get("active_project_name")
        return None

    def get_organization_id(self) -> Optional[str]:
        """Get the organization ID from config."""
        if self.config:
            return self.config.get("active_organization_id")
        return None

    def get_last_sync(self) -> Optional[str]:
        """Get the last sync timestamp (ISO format)."""
        return self._metadata.get("last_sync")

    def get_last_sync_direction(self) -> Optional[str]:
        """Get the last sync direction."""
        return self._metadata.get("last_sync_direction")

    def get_sync_history(self, limit: int = 10) -> list:
        """
        Get recent sync history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of sync records
        """
        history = self._metadata.get("sync_history", [])
        return history[-limit:]

    def is_paired(self) -> bool:
        """Check if project is paired with a Claude.ai project (from config)."""
        return self.get_project_id() is not None
