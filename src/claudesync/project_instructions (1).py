"""
Project instructions management for ClaudeSync.
Handles markdown-based project instructions that sync with Claude.ai.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ProjectInstructions:
    """Manages project instructions in markdown format."""
    
    def __init__(self, project_path: str):
        """
        Initialize project instructions manager.
        
        Args:
            project_path: Path to the ClaudeSync project directory
        """
        self.project_path = Path(project_path)
        self.claudesync_dir = self.project_path / '.claudesync'
        self.instructions_file = self.project_path / 'project-instructions.md'
        self.config_file = self.claudesync_dir / 'instructions.json'
    
    def create_instructions_template(self) -> bool:
        """
        Create a template project instructions file.
        
        Returns:
            True if created successfully, False if already exists
        """
        if self.instructions_file.exists():
            return False
        
        template_content = self._get_instructions_template()
        
        try:
            with open(self.instructions_file, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            # Create instructions config
            self._save_instructions_config({
                'enabled': True,
                'file_path': 'project-instructions.md',
                'auto_sync': True,
                'last_modified': None
            })
            
            logger.info(f"Created project instructions template: {self.instructions_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create instructions template: {e}")
            return False
    
    def _get_instructions_template(self) -> str:
        """Get the default project instructions template."""
        project_name = self.project_path.name
        
        return f"""# {project_name} - Project Instructions

## Project Overview
<!-- Describe what this project is for and its main purpose -->

## Architecture & Structure
<!-- Explain the project structure, key directories, and how code is organized -->

## Development Guidelines
<!-- Code style, conventions, and development practices -->

## Key Components
<!-- Important files, modules, or components to understand -->

## Dependencies & Setup
<!-- How to set up the development environment -->

## Common Tasks
<!-- Frequently performed tasks and how to do them -->

## Context for AI Assistance
<!-- Specific instructions for AI assistants working on this project -->

---
*This file is automatically synced with Claude.ai for AI assistance.*
*Edit this file in your preferred markdown editor (like Obsidian).*
"""
    
    def get_instructions_content(self) -> Optional[str]:
        """
        Get the current project instructions content.
        
        Returns:
            Instructions content as string, or None if not available
        """
        if not self.instructions_file.exists():
            return None
        
        try:
            with open(self.instructions_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read instructions: {e}")
            return None
    
    def update_instructions(self, content: str) -> bool:
        """
        Update project instructions content.
        
        Args:
            content: New instructions content
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with open(self.instructions_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update config with new modification time
            config = self._load_instructions_config()
            config['last_modified'] = self.instructions_file.stat().st_mtime
            self._save_instructions_config(config)
            
            logger.info("Updated project instructions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update instructions: {e}")
            return False
    
    def is_instructions_enabled(self) -> bool:
        """Check if project instructions are enabled for this project."""
        config = self._load_instructions_config()
        return config.get('enabled', False)
    
    def enable_instructions(self, enabled: bool = True):
        """Enable or disable project instructions syncing."""
        config = self._load_instructions_config()
        config['enabled'] = enabled
        self._save_instructions_config(config)
    
    def should_sync_instructions(self) -> bool:
        """
        Check if instructions should be synced based on file modification.
        
        Returns:
            True if instructions should be synced, False otherwise
        """
        if not self.is_instructions_enabled():
            return False
        
        if not self.instructions_file.exists():
            return False
        
        config = self._load_instructions_config()
        current_mtime = self.instructions_file.stat().st_mtime
        last_mtime = config.get('last_modified')
        
        return last_mtime is None or current_mtime > last_mtime
    
    def mark_synced(self):
        """Mark instructions as synced (update last modification time)."""
        if self.instructions_file.exists():
            config = self._load_instructions_config()
            config['last_modified'] = self.instructions_file.stat().st_mtime
            self._save_instructions_config(config)
    
    def get_instructions_info(self) -> Dict:
        """
        Get information about project instructions.
        
        Returns:
            Dictionary with instructions information
        """
        config = self._load_instructions_config()
        
        info = {
            'enabled': config.get('enabled', False),
            'file_exists': self.instructions_file.exists(),
            'file_path': str(self.instructions_file),
            'last_modified': config.get('last_modified'),
            'needs_sync': False
        }
        
        if info['file_exists']:
            current_mtime = self.instructions_file.stat().st_mtime
            info['current_mtime'] = current_mtime
            info['needs_sync'] = self.should_sync_instructions()
            
            # Get file size for display
            info['file_size'] = self.instructions_file.stat().st_size
        
        return info
    
    def _load_instructions_config(self) -> Dict:
        """Load instructions configuration."""
        if not self.config_file.exists():
            return {'enabled': False, 'auto_sync': True}
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {'enabled': False, 'auto_sync': True}
    
    def _save_instructions_config(self, config: Dict):
        """Save instructions configuration."""
        self.claudesync_dir.mkdir(exist_ok=True)
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save instructions config: {e}")


def get_instructions_for_sync(project_path: str) -> Optional[Dict[str, str]]:
    """
    Get project instructions formatted for syncing with Claude.ai.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with file info for syncing, or None if not available
    """
    instructions = ProjectInstructions(project_path)
    
    if not instructions.should_sync_instructions():
        return None
    
    content = instructions.get_instructions_content()
    if not content:
        return None
    
    return {
        'file_name': 'project-instructions.md',
        'content': content
    }
