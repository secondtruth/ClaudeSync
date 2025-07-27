import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import click
import time

class WorkspaceManager:
    """Manages multiple ClaudeSync projects in a workspace."""
    
    def __init__(self, workspace_config):
        self.config = workspace_config
    
    def discover_projects(self, root_path: Optional[str] = None) -> List[Dict]:
        """Discover all ClaudeSync projects in the workspace."""
        if root_path is None:
            root_path = self.config.get_workspace_root()
            if not root_path:
                if self.config.config.get("auto_discover", True):
                    # Auto-discover from current directory
                    root_path = os.getcwd()
                else:
                    return []
        
        projects = []
        exclude_patterns = self.config.config.get("exclude_patterns", [])
        max_depth = self.config.config.get("max_search_depth", 3)
        
        # Walk directory tree
        for root, dirs, files in os.walk(root_path):
            # Calculate depth
            depth = len(Path(root).relative_to(root_path).parts)
            if depth > max_depth:
                dirs.clear()  # Don't go deeper
                continue
            
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            # Check for .claudesync directory
            if '.claudesync' in dirs:
                config_file = os.path.join(root, '.claudesync', 'config.local.json')
                if os.path.exists(config_file):
                    try:
                        import json
                        with open(config_file, 'r') as f:
                            project_config = json.load(f)
                        
                        projects.append({
                            'path': root,
                            'name': project_config.get('active_project_name', 'Unknown'),
                            'id': project_config.get('active_project_id', 'Unknown'),
                            'relative_path': os.path.relpath(root, root_path)
                        })
                    except Exception:
                        # Invalid config, skip
                        pass
        
        return sorted(projects, key=lambda p: p['relative_path'])
    
    def sync_all_projects(self, projects: Optional[List[Dict]] = None,
                         parallel: bool = True,
                         dry_run: bool = False) -> List[Dict]:
        """Sync all projects in the workspace."""
        if projects is None:
            projects = self.discover_projects()
        
        if not projects:
            return []
        
        results = []
        
        if dry_run:
            click.echo("DRY RUN - Would sync the following projects:")
            for project in projects:
                click.echo(f"  - {project['name']} at {project['relative_path']}")
            return results
        
        if parallel:
            results = self._sync_parallel(projects)
        else:
            results = self._sync_sequential(projects)
        
        return results
    
    def _sync_parallel(self, projects: List[Dict]) -> List[Dict]:
        """Sync projects in parallel."""
        results = []
        
        with click.progressbar(length=len(projects), 
                             label='Syncing projects') as bar:
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                # Submit all sync tasks
                future_to_project = {
                    executor.submit(self._sync_single_project, project): project
                    for project in projects
                }
                
                # Process completed tasks
                for future in as_completed(future_to_project):
                    project = future_to_project[future]
                    try:
                        result = future.result(timeout=300)  # 5 minute timeout
                        results.append(result)
                    except Exception as e:
                        results.append({
                            'project': project['name'],
                            'path': project['path'],
                            'status': 'error',
                            'message': str(e),
                            'duration': 0
                        })
                    finally:
                        bar.update(1)
        
        return results
    
    def _sync_sequential(self, projects: List[Dict]) -> List[Dict]:
        """Sync projects sequentially."""
        results = []
        
        with click.progressbar(projects, 
                             label='Syncing projects',
                             item_show_func=lambda p: p['name'] if p else '') as bar:
            
            for project in bar:
                result = self._sync_single_project(project)
                results.append(result)
        
        return results
    
    def _sync_single_project(self, project: Dict) -> Dict:
        """Sync a single project."""
        start_time = time.time()
        
        try:
            # Run claudesync push
            result = subprocess.run(
                ['claudesync', 'push'],
                cwd=project['path'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return {
                    'project': project['name'],
                    'path': project['path'],
                    'status': 'success',
                    'message': 'Synced successfully',
                    'duration': duration
                }
            else:
                return {
                    'project': project['name'],
                    'path': project['path'],
                    'status': 'failed',
                    'message': result.stderr.strip() or 'Unknown error',
                    'duration': duration
                }
        
        except subprocess.TimeoutExpired:
            return {
                'project': project['name'],
                'path': project['path'],
                'status': 'timeout',
                'message': 'Sync timed out after 5 minutes',
                'duration': 300
            }
        except Exception as e:
            return {
                'project': project['name'],
                'path': project['path'],
                'status': 'error',
                'message': str(e),
                'duration': time.time() - start_time
            }
    
    def pull_all_chats(self, projects: Optional[List[Dict]] = None,
                      safety_options: Dict = None) -> List[Dict]:
        """Pull chats for all projects."""
        if projects is None:
            projects = self.discover_projects()
        
        if not projects:
            return []
        
        results = []
        safety_args = []
        
        if safety_options:
            if safety_options.get('dry_run'):
                safety_args.append('--dry-run')
            if safety_options.get('backup_existing'):
                safety_args.append('--backup-existing')
        
        with click.progressbar(projects,
                             label='Pulling chats',
                             item_show_func=lambda p: p['name'] if p else '') as bar:
            
            for project in bar:
                try:
                    cmd = ['claudesync', 'chat', 'pull'] + safety_args
                    result = subprocess.run(
                        cmd,
                        cwd=project['path'],
                        capture_output=True,
                        text=True,
                        timeout=120  # 2 minute timeout
                    )
                    
                    if result.returncode == 0:
                        results.append({
                            'project': project['name'],
                            'status': 'success',
                            'message': 'Chats pulled successfully'
                        })
                    else:
                        results.append({
                            'project': project['name'],
                            'status': 'failed',
                            'message': result.stderr.strip() or 'Unknown error'
                        })
                
                except Exception as e:
                    results.append({
                        'project': project['name'],
                        'status': 'error',
                        'message': str(e)
                    })
        
        return results
    
    def get_status(self, projects: Optional[List[Dict]] = None) -> Dict:
        """Get status summary for all projects."""
        if projects is None:
            projects = self.discover_projects()
        
        status = {
            'workspace_root': self.config.get_workspace_root() or 'Auto-discovery',
            'total_projects': len(projects),
            'projects': []
        }
        
        for project in projects:
            # Check for file watcher
            pid_file = os.path.join(project['path'], '.claudesync', 'watch.pid')
            watcher_running = False
            
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)  # Check if process exists
                    watcher_running = True
                except:
                    pass
            
            status['projects'].append({
                'name': project['name'],
                'path': project['relative_path'],
                'watcher': 'running' if watcher_running else 'stopped'
            })
        
        return status