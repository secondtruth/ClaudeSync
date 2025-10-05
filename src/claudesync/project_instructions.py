import os
import json
from datetime import datetime
from typing import Optional, Dict, Tuple

class ProjectInstructions:
    """Manages project instructions syncing with Claude.ai API."""
    
    INSTRUCTIONS_FILE = "PROJECT_INSTRUCTIONS.md"
    CONFIG_FILE = ".claudesync/instructions.json"
    
    DEFAULT_CONFIG = {
        "enabled": True,
        "file_path": INSTRUCTIONS_FILE,
        "auto_sync": True,
        "last_synced": None,
        "last_remote_update": None
    }
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.config_path = os.path.join(project_path, self.CONFIG_FILE)
        self.config = self._load_config()
        self.config['file_path'] = self.INSTRUCTIONS_FILE
        self.instructions_path = os.path.join(project_path, self.config['file_path'])
    
    def _load_config(self) -> Dict:
        """Load instructions configuration."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in self.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception:
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """Save instructions configuration."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def pull_instructions(self, provider, organization_id: str, project_id: str) -> bool:
        """Pull instructions from Claude.ai and save to local .md file."""
        if not self.config['enabled']:
            return False
        
        try:
            # Get project details from API
            project = provider.get_project_details(organization_id, project_id)
            
            # The VSCode extension uses 'prompt_template' as the field name
            instructions = project.get('prompt_template', '')
            
            # Save to local .md file
            with open(self.instructions_path, 'w', encoding='utf-8') as f:
                f.write(instructions)
            
            # Update config
            self.config['last_synced'] = datetime.now().isoformat()
            self.config['last_remote_update'] = project.get('updated_at')
            self._save_config()
            
            return True
            
        except Exception as e:
            import logging
            logging.error(f"Failed to pull project instructions: {e}")
            return False
    
    def push_instructions(self, provider, organization_id: str, project_id: str) -> bool:
        """Push local .md file to update project instructions in Claude.ai."""
        if not self.config['enabled']:
            return False
        
        if not os.path.exists(self.instructions_path):
            return False
        
        try:
            # Read local instructions
            with open(self.instructions_path, 'r', encoding='utf-8') as f:
                instructions = f.read()
            
            # Update via API
            provider.update_project_instructions(organization_id, project_id, instructions)
            
            # Update config
            self.config['last_synced'] = datetime.now().isoformat()
            self._save_config()
            
            return True
            
        except Exception as e:
            import logging
            logging.error(f"Failed to push project instructions: {e}")
            return False
    
    def sync_instructions(self, provider, organization_id: str, project_id: str, 
                         direction: str = "both") -> Dict[str, bool]:
        """Sync instructions in specified direction."""
        results = {"pulled": False, "pushed": False}
        
        if direction in ["pull", "both"]:
            results["pulled"] = self.pull_instructions(provider, organization_id, project_id)
        
        if direction in ["push", "both"]:
            results["pushed"] = self.push_instructions(provider, organization_id, project_id)
        
        return results
    
    def is_enabled(self) -> bool:
        """Check if instructions syncing is enabled."""
        return self.config.get('enabled', True)
    
    def enable(self):
        """Enable instructions syncing."""
        self.config['enabled'] = True
        self._save_config()
    
    def disable(self):
        """Disable instructions syncing."""
        self.config['enabled'] = False
        self._save_config()
    
    def get_status(self) -> Dict:
        """Get instructions status."""
        exists = os.path.exists(self.instructions_path)
        
        status = {
            'enabled': self.config['enabled'],
            'exists': exists,
            'path': self.config['file_path'],
            'auto_sync': self.config.get('auto_sync', True),
            'last_synced': self.config.get('last_synced'),
            'last_remote_update': self.config.get('last_remote_update')
        }
        
        if exists:
            stat = os.stat(self.instructions_path)
            status['size'] = stat.st_size
            status['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        
        return status
    
    def initialize(self, force: bool = False) -> bool:
        """Initialize with empty instructions file."""
        if os.path.exists(self.instructions_path) and not force:
            return False
        
        # Create empty file
        with open(self.instructions_path, 'w') as f:
            f.write("# Project Instructions\n\n")
        
        self._save_config()
        return True
