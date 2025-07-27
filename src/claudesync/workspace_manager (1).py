"""
Simple workspace management for ClaudeSync.
Provides multi-project operations without hardcoded paths.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional
from .workspace_config import WorkspaceConfig

logger = logging.getLogger(__name__)


class ProjectInfo:
    """Information about a discovered ClaudeSync project."""
    
    def __init__(self, path: str, name: str = None):
        self.path = Path(path)
        self.name = name or self.path.name
        
    def __str__(self):
        return f"{self.name} ({self.path})"


class WorkspaceManager:
    """Manages multiple ClaudeSync projects."""
    
    def __init__(self):
        self.discovered_projects: List[ProjectInfo] = []
        
    def discover_projects(self, search_paths: List[str], max_depth: int = 3) -> List[ProjectInfo]:
        """
        Discover all ClaudeSync projects in the given search paths.
        
        Args:
            search_paths: Directories to search for projects
            max_depth: Maximum depth to search (prevents infinite recursion)
            
        Returns:
            List of discovered ProjectInfo objects
        """
        projects = []
        
        for search_path in search_paths:
            path = Path(search_path)
            if not path.exists():
                logger.warning(f"Search path does not exist: {search_path}")
                continue
                
            logger.info(f"Searching for projects in: {search_path}")
            found = self._find_projects_recursive(path, max_depth)
            projects.extend(found)
            logger.info(f"Found {len(found)} projects in {search_path}")
        
        self.discovered_projects = projects
        return projects
    
    def _find_projects_recursive(self, path: Path, max_depth: int) -> List[ProjectInfo]:
        """Recursively find ClaudeSync projects."""
        if max_depth <= 0:
            return []
            
        projects = []
        
        try:
            # Check if current directory is a ClaudeSync project
            if (path / '.claudesync').is_dir():
                projects.append(ProjectInfo(str(path)))
                # Don't search subdirectories of a project
                return projects
            
            # Search subdirectories
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    projects.extend(self._find_projects_recursive(item, max_depth - 1))
                    
        except PermissionError:
            logger.warning(f"Permission denied accessing: {path}")
        except Exception as e:
            logger.warning(f"Error searching {path}: {e}")
            
        return projects
    
    def sync_all_projects(self, projects: List[ProjectInfo] = None) -> Dict[str, bool]:
        """
        Sync all discovered projects.
        
        Args:
            projects: Optional list of projects to sync. Uses discovered_projects if None.
            
        Returns:
            Dictionary mapping project names to success status
        """
        if projects is None:
            projects = self.discovered_projects
            
        if not projects:
            logger.warning("No projects to sync")
            return {}
        
        results = {}
        
        for project in projects:
            logger.info(f"Syncing project: {project.name}")
            success = self._sync_project(project)
            results[project.name] = success
            
        return results
    
    def _sync_project(self, project: ProjectInfo) -> bool:
        """
        Sync a single project.
        
        Args:
            project: Project to sync
            
        Returns:
            True if sync succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["claudesync", "push"],
                cwd=str(project.path),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per project
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully synced {project.name}")
                return True
            else:
                logger.error(f"❌ Failed to sync {project.name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️ Timeout syncing {project.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error syncing {project.name}: {e}")
            return False
    
    def chat_pull_all_projects(self, projects: List[ProjectInfo] = None, 
                              dry_run: bool = False, backup_existing: bool = False, 
                              force: bool = False) -> Dict[str, bool]:
        """
        Pull chats for all discovered projects.
        
        Args:
            projects: Optional list of projects. Uses discovered_projects if None.
            dry_run: Preview mode without making changes
            backup_existing: Create backup of existing files
            force: Skip confirmation prompts
            
        Returns:
            Dictionary mapping project names to success status
        """
        if projects is None:
            projects = self.discovered_projects
            
        if not projects:
            logger.warning("No projects to pull chats for")
            return {}
        
        results = {}
        
        for project in projects:
            logger.info(f"Pulling chats for: {project.name}")
            success = self._chat_pull_project(project, dry_run, backup_existing, force)
            results[project.name] = success
            
        return results
    
    def _chat_pull_project(self, project: ProjectInfo, dry_run: bool = False, 
                          backup_existing: bool = False, force: bool = False) -> bool:
        """
        Pull chats for a single project.
        
        Args:
            project: Project to pull chats for
            dry_run: Preview mode without making changes
            backup_existing: Create backup of existing files  
            force: Skip confirmation prompts
            
        Returns:
            True if pull succeeded, False otherwise
        """
        try:
            # Build command with safety options
            cmd = ["claudesync", "chat", "pull"]
            
            if dry_run:
                cmd.append("--dry-run")
            if backup_existing:
                cmd.append("--backup-existing")
            if force:
                cmd.append("--force")
            
            result = subprocess.run(
                cmd,
                cwd=str(project.path),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per project
            )
            
            if result.returncode == 0:
                if dry_run:
                    logger.info(f"🔍 Chat pull preview completed for {project.name}")
                else:
                    logger.info(f"✅ Successfully pulled chats for {project.name}")
                return True
            else:
                logger.error(f"❌ Failed to pull chats for {project.name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️ Timeout pulling chats for {project.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error pulling chats for {project.name}: {e}")
            return False


def get_default_search_paths() -> List[str]:
    """
    Get search paths based on workspace configuration.
    
    Returns:
        List of search paths to look for projects
    """
    config = WorkspaceConfig()
    return config.get_search_paths()
