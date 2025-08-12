"""
Dynamic Configuration Manager for ClaudeSync

This module provides a more resilient configuration system that:
1. Only stores minimal project_id in local configs
2. Dynamically resolves paths, names, and organizations at runtime
3. Auto-discovers projects by folder name matching
4. Self-heals broken configurations
"""

import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DynamicConfigManager:
    """
    A configuration manager that dynamically resolves configuration values
    at runtime rather than storing them statically.
    """
    
    MINIMAL_CONFIG_KEYS = {'active_project_id'}  # Only store what's absolutely necessary
    DYNAMIC_KEYS = {
        'local_path',  # Always use current directory
        'active_project_name',  # Fetch from API
        'active_organization_id',  # Use global active org
    }
    
    def __init__(self, base_config_manager):
        """Initialize with a reference to the existing config manager."""
        self.base = base_config_manager
        self._provider = None
        self._project_cache = {}
        
    @property
    def provider(self):
        """Lazy load the provider."""
        if self._provider is None:
            from claudesync.provider_factory import get_provider
            self._provider = get_provider(self.base)
        return self._provider
    
    def get(self, key: str, default=None):
        """
        Get a configuration value, resolving dynamically when appropriate.
        """
        # For minimal config keys, use stored value (direct access to avoid recursion)
        if key in self.MINIMAL_CONFIG_KEYS:
            return self.base.local_config.get(key) or self.base.global_config.get(key, default)
        
        # For dynamic keys, resolve at runtime
        if key == 'local_path':
            return self._get_dynamic_local_path()
        elif key == 'active_project_name':
            return self._get_dynamic_project_name()
        elif key == 'active_organization_id':
            return self._get_dynamic_organization_id()
        
        # For everything else, use base config (direct access to avoid recursion)
        return self.base.local_config.get(key) or self.base.global_config.get(key, default)
    
    def _get_dynamic_local_path(self) -> str:
        """Always return the current working directory or project directory."""
        # If we're in a .claudesync directory, go up one level
        current_path = Path.cwd()
        if current_path.name == '.claudesync':
            current_path = current_path.parent
        
        # If local_config_dir is set, use that
        if hasattr(self.base, 'local_config_dir') and self.base.local_config_dir:
            return str(self.base.local_config_dir)
        
        return str(current_path)
    
    def _get_dynamic_project_name(self) -> Optional[str]:
        """Fetch project name from API using project_id."""
        project_id = self.base.local_config.get('active_project_id')  # Direct access to avoid recursion
        if not project_id:
            return None
        
        # Check cache first
        if project_id in self._project_cache:
            return self._project_cache[project_id]['name']
        
        try:
            # Fetch from API
            org_id = self._get_dynamic_organization_id()
            if org_id:
                projects = self.provider.list_projects(org_id, include_archived=False)
                for project in projects:
                    if project['id'] == project_id:
                        self._project_cache[project_id] = project
                        return project['name']
        except Exception as e:
            logger.debug(f"Could not fetch project name: {e}")
        
        # Fallback to stored value if API fails
        return self.base.local_config.get('active_project_name')  # Direct access to avoid recursion
    
    def _get_dynamic_organization_id(self) -> Optional[str]:
        """Use the globally active organization."""
        # First check environment variable (for subprocess context)
        env_org = os.environ.get('CLAUDESYNC_ORG_ID')
        if env_org:
            return env_org
            
        # Then check if there's a global active org
        global_org = self.base.global_config.get('active_organization_id')
        if global_org:
            return global_org
        
        # Fallback to local config
        return self.base.local_config.get('active_organization_id')  # Direct access to avoid recursion
    
    def auto_discover_project(self, folder_path: Optional[str] = None) -> Optional[str]:
        """
        Attempt to discover the project ID based on folder name.
        
        Returns:
            Project ID if found, None otherwise
        """
        if folder_path is None:
            folder_path = self._get_dynamic_local_path()
        
        folder_name = Path(folder_path).name
        
        # Clean the folder name for matching (remove emojis and special chars)
        clean_name = re.sub(r'[^\w\s-]', '', folder_name).strip()
        
        try:
            org_id = self._get_dynamic_organization_id()
            if not org_id:
                return None
            
            projects = self.provider.list_projects(org_id, include_archived=False)
            
            # Try exact match first
            for project in projects:
                project_clean = re.sub(r'[^\w\s-]', '', project['name']).strip()
                if project_clean.lower() == clean_name.lower():
                    logger.info(f"Auto-discovered project: {project['name']}")
                    return project['id']
            
            # Try fuzzy match
            best_match = None
            best_score = 0.0
            
            for project in projects:
                project_clean = re.sub(r'[^\w\s-]', '', project['name']).strip()
                score = SequenceMatcher(None, clean_name.lower(), project_clean.lower()).ratio()
                
                if score > best_score and score > 0.8:  # 80% similarity threshold
                    best_score = score
                    best_match = project
            
            if best_match:
                logger.info(f"Auto-discovered project (fuzzy match): {best_match['name']}")
                return best_match['id']
                
        except Exception as e:
            logger.debug(f"Auto-discovery failed: {e}")
        
        return None
    
    def heal_config(self, project_path: str) -> bool:
        """
        Attempt to fix a broken configuration.
        
        Returns:
            True if config was healed, False otherwise
        """
        config_file = Path(project_path) / '.claudesync' / 'config.local.json'
        
        if not config_file.exists():
            return False
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Extract only minimal config
            minimal_config = {
                k: v for k, v in config.items() 
                if k in self.MINIMAL_CONFIG_KEYS and v is not None
            }
            
            # If we don't have a project_id, try to discover it
            if 'active_project_id' not in minimal_config:
                discovered_id = self.auto_discover_project(project_path)
                if discovered_id:
                    minimal_config['active_project_id'] = discovered_id
                else:
                    return False
            
            # Save minimal config
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(minimal_config, f, indent=2)
            
            logger.info(f"Healed configuration for {project_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to heal config: {e}")
            return False
    
    def create_minimal_config(self, project_id: str, project_path: str) -> bool:
        """
        Create a minimal configuration file with just the project ID.
        """
        config_dir = Path(project_path) / '.claudesync'
        config_dir.mkdir(exist_ok=True)
        
        config_file = config_dir / 'config.local.json'
        
        minimal_config = {
            'active_project_id': project_id
        }
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(minimal_config, f, indent=2)
            
            logger.info(f"Created minimal config for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create minimal config: {e}")
            return False
