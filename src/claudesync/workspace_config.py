import os
import json
from pathlib import Path
from typing import Optional, List, Dict

class WorkspaceConfig:
    """Manages workspace configuration for ClaudeSync."""
    
    CONFIG_FILE = os.path.expanduser("~/.claudesync/workspace.json")
    
    DEFAULT_CONFIG = {
        "workspace_root": None,
        "auto_discover": True,
        "max_search_depth": 3,
        "exclude_patterns": [
            ".git", "__pycache__", "node_modules", 
            ".vscode", ".idea", "venv", ".env"
        ]
    }
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default."""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    for key, value in self.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception:
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Save configuration to file."""
        os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def set_workspace_root(self, path: str):
        """Set the workspace root directory."""
        # Expand and resolve path
        resolved_path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(resolved_path):
            raise ValueError(f"Path does not exist: {resolved_path}")
        
        if not os.path.isdir(resolved_path):
            raise ValueError(f"Path is not a directory: {resolved_path}")
        
        self.config["workspace_root"] = resolved_path
        self._save_config()
    
    def get_workspace_root(self) -> Optional[str]:
        """Get the configured workspace root."""
        return self.config.get("workspace_root")
    
    def reset(self):
        """Reset configuration to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config()
    
    def add_exclude_pattern(self, pattern: str):
        """Add an exclude pattern."""
        if pattern not in self.config["exclude_patterns"]:
            self.config["exclude_patterns"].append(pattern)
            self._save_config()
    
    def remove_exclude_pattern(self, pattern: str):
        """Remove an exclude pattern."""
        if pattern in self.config["exclude_patterns"]:
            self.config["exclude_patterns"].remove(pattern)
            self._save_config()
    
    def set_auto_discover(self, enabled: bool):
        """Enable or disable auto-discovery."""
        self.config["auto_discover"] = enabled
        self._save_config()
    
    def set_max_search_depth(self, depth: int):
        """Set maximum search depth for project discovery."""
        if depth < 1:
            raise ValueError("Search depth must be at least 1")
        self.config["max_search_depth"] = depth
        self._save_config()
    
    def get_config(self) -> Dict:
        """Get the full configuration."""
        return self.config.copy()