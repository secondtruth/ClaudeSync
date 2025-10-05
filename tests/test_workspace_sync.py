"""Tests for workspace sync functionality."""
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import json

from claudesync.workspace_sync import WorkspaceSync


class TestWorkspaceSync(unittest.TestCase):
    """Test workspace sync operations."""

    def setUp(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = Path(self.temp_dir)
        self.mock_provider = Mock()
        self.syncer = WorkspaceSync(self.workspace_root, self.mock_provider)

    def test_init(self):
        """Test WorkspaceSync initialization."""
        self.assertEqual(self.syncer.root, self.workspace_root)
        self.assertTrue(self.syncer.config_dir.exists())
        self.assertIsNotNone(self.syncer.config)

    def test_sanitize_name(self):
        """Test folder name sanitization with emojis."""
        # Test emoji preservation
        self.assertEqual(self.syncer._sanitize_name("Project 🚀"), "Project 🚀")
        self.assertEqual(self.syncer._sanitize_name("Data 📊 Analysis"), "Data 📊 Analysis")

        # Test removing invalid characters
        self.assertEqual(self.syncer._sanitize_name("Project/Test"), "ProjectTest")
        self.assertEqual(self.syncer._sanitize_name("File:Name"), "FileName")

        # Test empty name handling
        self.assertEqual(self.syncer._sanitize_name(""), "unnamed_project")

    def test_sync_all_no_projects(self):
        """Test sync with no projects."""
        self.mock_provider.get_organizations.return_value = [{"id": "org1", "name": "Test Org"}]
        self.mock_provider.get_projects.return_value = []

        stats = self.syncer.sync_all()

        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(stats["skipped"], 0)

    def test_sync_all_with_projects(self):
        """Test sync with projects."""
        self.mock_provider.get_organizations.return_value = [{"id": "org1", "name": "Test Org"}]
        self.mock_provider.get_projects.return_value = [
            {"id": "proj1", "name": "Project 1"},
            {"id": "proj2", "name": "Project 🚀"}
        ]
        self.mock_provider.list_files.return_value = []
        self.mock_provider.get_project_instructions.return_value = {}

        stats = self.syncer.sync_all(dry_run=True)

        self.assertEqual(stats["created"], 2)
        self.assertEqual(stats["skipped"], 0)
        self.mock_provider.get_projects.assert_called_once()

    def test_bidirectional_sync(self):
        """Test bidirectional sync functionality."""
        self.mock_provider.get_organizations.return_value = [{"id": "org1", "name": "Test Org"}]
        self.mock_provider.get_projects.return_value = [{"id": "proj1", "name": "Project 1"}]
        self.mock_provider.list_files.return_value = []
        self.mock_provider.get_project_instructions.return_value = {}
        self.mock_provider.upload_file = Mock()

        # Create local file
        project_dir = self.workspace_root / "Project 1"
        project_dir.mkdir()
        test_file = project_dir / "test.py"
        test_file.write_text("print('test')")

        stats = self.syncer.sync_all(bidirectional=True)

        # Should have attempted upload
        self.assertGreater(stats.get("uploaded", 0), 0)

    def test_conflict_resolution(self):
        """Test conflict resolution strategies."""
        # Test remote strategy (default)
        result = self.syncer._resolve_conflict("remote", {}, {})
        self.assertFalse(result)

        # Test local strategy
        result = self.syncer._resolve_conflict("local", {}, {})
        self.assertTrue(result)

        # Test newer strategy
        result = self.syncer._resolve_conflict("newer", {}, {})
        self.assertTrue(result)

    def test_chat_sync(self):
        """Test chat synchronization."""
        self.mock_provider.get_chat_conversations.return_value = [
            {"uuid": "chat1", "name": "Test Chat", "created_at": "2024-01-01"}
        ]
        self.mock_provider.get_chat_conversation.return_value = {
            "chat_messages": [
                {"sender": "user", "text": "Hello"},
                {"sender": "assistant", "text": "Hi there!"}
            ]
        }

        count = self.syncer._sync_chats("org1", dry_run=False)

        self.assertEqual(count, 1)
        chats_dir = self.workspace_root / "claude_chats"
        self.assertTrue(chats_dir.exists())

    def test_system_instructions_sync(self):
        """Test AGENTS.md sync."""
        self.mock_provider.get_organizations.return_value = [{"id": "org1", "name": "Test Org"}]
        self.mock_provider.get_projects.return_value = [{"id": "proj1", "name": "Project 1"}]
        self.mock_provider.list_files.return_value = []
        self.mock_provider.get_project_instructions.return_value = {
            "template": "You are a helpful assistant."
        }

        stats = self.syncer.sync_all()

        # Check AGENTS.md was created
        agents_file = self.workspace_root / "Project 1" / "AGENTS.md"
        self.assertTrue(agents_file.exists())
        self.assertEqual(agents_file.read_text(), "You are a helpful assistant.")

    def test_config_persistence(self):
        """Test configuration save/load."""
        # Add project mapping
        self.syncer.config["project_map"]["test_id"] = "Test Project"
        self.syncer._save_config()

        # Create new syncer to test loading
        new_syncer = WorkspaceSync(self.workspace_root, self.mock_provider)
        self.assertEqual(new_syncer.config["project_map"]["test_id"], "Test Project")

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()