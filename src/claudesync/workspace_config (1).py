"""
Simple workspace configuration for ClaudeSync.
Allows setting a dedicated workspace directory.
"""

import json
import os
from pathlib import Path
from typing import Optional

class WorkspaceConfig:
    """Manages workspace configuration settings."""
    
    def __init__(self):
        self.config_file = Path.home() / '.claudesync' / 'workspace.json'
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load workspace configuration from file."""
        if not self.config_file.exists():
            return self._get_default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Ensure all required keys exist
                default_config = self._get_default_config()
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except (json.JSONDecodeError, FileNotFoundError):
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Get default workspace configuration."""
        return {
            'workspace_root': None,
            'auto_discover': True,
            'max_search_depth': 3,
            'exclude_patterns': ['.git', '__pycache__', 'node_modules', '.vscode', '.idea']
        }
    
    def _save_config(self):
        """Save workspace configuration to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def set_workspace_root(self, path: str) -> bool:
        """
        Set the workspace root directory.
        
        Args:
            path: Path to workspace root directory
            
        Returns:
            True if successful, False if path doesn't exist
        """
        workspace_path = Path(path).resolve()
        if not workspace_path.exists():
            return False
        
        self.config['workspace_root'] = str(workspace_path)
        self._save_config()
        return True
    
    def get_workspace_root(self) -> Optional[str]:
        """Get the configured workspace root directory."""
        return self.config.get('workspace_root')
    
    def get_search_paths(self) -> list:
        """
        Get search paths for project discovery.
        
        Returns:
            List of paths to search for projects
        """
        workspace_root = self.get_workspace_root()
        
        if workspace_root and Path(workspace_root).exists():
            # Use configured workspace root
            return [workspace_root]
        
        if self.config.get('auto_discover', True):
            # Fall back to auto-discovery
            return self._get_default_search_paths()
        
        return []
    
    def _get_default_search_paths(self) -> list:
        """Get default search paths when no workspace is configured."""
        search_paths = []
        
        # Add current working directory
        search_paths.append(os.getcwd())
        
        # Add common project directories
        home = Path.home()
        common_dirs = [
            "Documents",
            "Projects", 
            "Development",
            "dev",
            "workspace",
            "code"
        ]
        
        for dir_name in common_dirs:
            potential_path = home / dir_name
            if potential_path.exists():
                search_paths.append(str(potential_path))
        
        # Add some common nested paths
        nested_paths = [
            "Documents/GitHub",
            "Documents/Projects", 
            "Documents/Development",
            "Documents/Obsidian"
        ]
        
        for nested_path in nested_paths:
            potential_path = home / nested_path
            if potential_path.exists():
                search_paths.append(str(potential_path))
        
        return search_paths
    
    def get_max_search_depth(self) -> int:
        """Get maximum search depth for project discovery."""
        return self.config.get('max_search_depth', 3)
    
    def set_max_search_depth(self, depth: int):
        """Set maximum search depth for project discovery."""
        self.config['max_search_depth'] = max(1, depth)
        self._save_config()
    
    def get_exclude_patterns(self) -> list:
        """Get patterns to exclude from project discovery."""
        return self.config.get('exclude_patterns', [])
    
    def add_exclude_pattern(self, pattern: str):
        """Add a pattern to exclude from project discovery."""
        patterns = self.get_exclude_patterns()
        if pattern not in patterns:
            patterns.append(pattern)
            self.config['exclude_patterns'] = patterns
            self._save_config()
    
    def remove_exclude_pattern(self, pattern: str):
        """Remove a pattern from exclusion list."""
        patterns = self.get_exclude_patterns()
        if pattern in patterns:
            patterns.remove(pattern)
            self.config['exclude_patterns'] = patterns
            self._save_config()
    
    def is_auto_discover_enabled(self) -> bool:
        """Check if auto-discovery is enabled."""
        return self.config.get('auto_discover', True)
    
    def set_auto_discover(self, enabled: bool):
        """Enable or disable auto-discovery."""
        self.config['auto_discover'] = enabled
        self._save_config()
    
    def get_config_summary(self) -> dict:
        """Get a summary of current configuration."""
        workspace_root = self.get_workspace_root()
        return {
            'workspace_root': workspace_root,
            'workspace_exists': workspace_root and Path(workspace_root).exists(),
            'auto_discover': self.is_auto_discover_enabled(),
            'max_search_depth': self.get_max_search_depth(),
            'exclude_patterns': self.get_exclude_patterns(),
            'search_paths': self.get_search_paths()
        }
