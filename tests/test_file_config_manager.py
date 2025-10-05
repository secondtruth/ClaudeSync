import json
from pathlib import Path

from claudesync.configmanager.file_config_manager import FileConfigManager


def test_local_config_persists_without_existing_project_folder(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    def fake_find(self, max_depth=100):
        config_dir = workspace / ".claudesync"
        return workspace if config_dir.exists() else None

    monkeypatch.setattr(FileConfigManager, "_find_local_config_dir", fake_find)

    manager = FileConfigManager()

    manager.set("active_provider", "claude.ai", local=True)
    manager.set("active_organization_id", "org-123", local=True)

    config_dir = workspace / ".claudesync"
    config_file = config_dir / "config.local.json"

    assert config_file.exists()

    data = json.loads(config_file.read_text())
    assert data["active_provider"] == "claude.ai"
    assert data["active_organization_id"] == "org-123"

    reloaded = FileConfigManager()
    assert reloaded.local_config_dir == workspace
    assert reloaded.get_active_provider() == "claude.ai"
    assert reloaded.get("active_organization_id") == "org-123"
