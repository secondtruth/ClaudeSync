import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import click
import time
import json
import logging

logger = logging.getLogger(__name__)

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
                        
                        # Don't descend into this project directory  
                        dirs.clear()
                    except Exception:
                        # Invalid config, skip
                        pass
        
        return sorted(projects, key=lambda p: p['relative_path'])
    
    def analyze_project_changes(self, project: Dict, sync_options: Dict) -> Dict:
        """Analyze what changes would be made to a project during sync."""
        stats = {
            'files_to_push': 0,
            'files_to_pull': 0,
            'files_to_delete_remote': 0,
            'files_to_delete_local': 0,
            'instructions_status': None,
            'conflicts_detected': 0
        }
        
        try:
            # Run csync in analysis mode (we'll need a dry-run that outputs JSON)
            # For now, simulate the analysis
            project_path = project['path']
            
            # Check for local files
            local_files = []
            for root, dirs, files in os.walk(project_path):
                # Skip .claudesync and other ignored directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != 'node_modules']
                
                for file in files:
                    if not file.startswith('.'):
                        local_files.append(os.path.join(root, file))
            
            # Estimate changes (this is simplified - real implementation would query API)
            stats['files_to_push'] = len(local_files)
            
            # Check for project instructions
            instructions_file = os.path.join(project_path, 'project-instructions.md')
            old_instructions_file = os.path.join(project_path, '.projectinstructions')
            
            if os.path.exists(instructions_file):
                stats['instructions_status'] = 'Will update'
            elif os.path.exists(old_instructions_file):
                stats['instructions_status'] = 'Will rename and update'
            elif sync_options.get('with_instructions'):
                stats['instructions_status'] = 'Will create'
            
            # For actual implementation, would need to:
            # 1. Query remote files via API
            # 2. Compare checksums
            # 3. Detect actual conflicts
            # 4. Count actual changes
            
            # Simplified estimation
            if sync_options.get('pull_only'):
                stats['files_to_push'] = 0
                stats['files_to_pull'] = 5  # Estimate
            elif sync_options.get('push_only'):
                stats['files_to_pull'] = 0
            else:
                stats['files_to_pull'] = 2  # Estimate
            
            if not sync_options.get('prune_remote'):
                stats['files_to_delete_remote'] = 0
            else:
                stats['files_to_delete_remote'] = 1  # Estimate
                
        except Exception as e:
            # If analysis fails, return zeros
            pass
        
        return stats
    
    def sync_all_projects(self, projects: Optional[List[Dict]] = None,
                         sync_options: Optional[Dict] = None,
                         parallel: bool = True,
                         dry_run: bool = False) -> List[Dict]:
        """Sync all projects in the workspace with options."""
        if projects is None:
            projects = self.discover_projects()
        
        if not projects:
            return []
        
        if sync_options is None:
            sync_options = {}
        
        results = []
        
        if dry_run:
            click.echo("DRY RUN - Would sync the following projects:")
            for project in projects:
                click.echo(f"  - {project['name']} at {project['relative_path']}")
            return results
        
        parallel_workers = sync_options.get('parallel_workers', 4)
        
        if parallel and parallel_workers > 1:
            results = self._sync_parallel(projects, sync_options, parallel_workers)
        else:
            results = self._sync_sequential(projects, sync_options)
        
        return results
    
    def _sync_parallel(self, projects: List[Dict], sync_options: Dict, max_workers: int = 4) -> List[Dict]:
        """Sync projects in parallel."""
        results = []
        
        with click.progressbar(length=len(projects), 
                             label='Syncing projects') as bar:
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all sync tasks
                future_to_project = {
                    executor.submit(self._sync_single_project, project, sync_options): project
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
    
    def _sync_sequential(self, projects: List[Dict], sync_options: Dict) -> List[Dict]:
        """Sync projects sequentially."""
        results = []
        
        with click.progressbar(projects, 
                             label='Syncing projects',
                             item_show_func=lambda p: p['name'] if p else '') as bar:
            
            for project in bar:
                result = self._sync_single_project(project, sync_options)
                results.append(result)
        
        return results
    
    def _sync_single_project(self, project: Dict, sync_options: Dict) -> Dict:
        """Sync a single project with options."""
        start_time = time.time()
        
        try:
            # Build command based on options
            cmd = ['csync']
            
            # Temporarily set config options if needed
            config_cmds = []
            
            if not sync_options.get('prune_remote', True):
                config_cmds.append(['csync', 'config', 'set', 'prune_remote_files', 'false'])
            
            if sync_options.get('two_way_sync'):
                config_cmds.append(['csync', 'config', 'set', 'two_way_sync', 'true'])
            
            # Run config commands
            for config_cmd in config_cmds:
                subprocess.run(config_cmd, cwd=project['path'], capture_output=True, text=True,
                              encoding='utf-8', errors='replace')
            
            # Determine sync direction
            if sync_options.get('pull_only'):
                # Pull instructions first if enabled
                if sync_options.get('with_instructions', True):  # Default to True
                    instructions_result = subprocess.run(
                        ['csync', 'project', 'instructions', 'pull'],
                        cwd=project['path'],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=30
                    )
                    # Don't fail if instructions pull fails
                    if instructions_result.returncode != 0:
                        logger.debug(f"Instructions pull failed for {project['name']}: {instructions_result.stderr}")
                
                # Then do regular pull
                cmd.append('pull')
                if sync_options.get('conflict_strategy') == 'local-wins':
                    cmd.append('--merge')
                elif sync_options.get('conflict_strategy') == 'remote-wins':
                    cmd.append('--force')
            elif sync_options.get('push_only'):
                # Push instructions first if they exist locally
                if sync_options.get('with_instructions', True):  # Default to True
                    instructions_file = os.path.join(project['path'], 'project-instructions.md')
                    if os.path.exists(instructions_file):
                        instructions_result = subprocess.run(
                            ['csync', 'project', 'instructions', 'push'],
                            cwd=project['path'],
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=30
                        )
                        # Don't fail if instructions push fails
                        if instructions_result.returncode != 0:
                            logger.debug(f"Instructions push failed for {project['name']}: {instructions_result.stderr}")
                
                # Then do regular push
                cmd.append('push')
            else:
                # Bidirectional sync
                if sync_options.get('two_way_sync'):
                    # Sync instructions first
                    if sync_options.get('with_instructions', True):  # Default to True
                        instructions_result = subprocess.run(
                            ['csync', 'project', 'instructions', 'sync'],
                            cwd=project['path'],
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=30
                        )
                        # Don't fail if instructions sync fails
                        if instructions_result.returncode != 0:
                            logger.debug(f"Instructions sync failed for {project['name']}: {instructions_result.stderr}")
                    
                    # Then do regular sync
                    cmd.append('sync')
                    cmd.extend(['--conflict-strategy', sync_options.get('conflict_strategy', 'prompt')])
                else:
                    # Standard sync: always sync instructions first, then pull, then push
                    
                    # Step 1: Sync project instructions explicitly
                    if sync_options.get('with_instructions', True):  # Default to True
                        instructions_result = subprocess.run(
                            ['csync', 'project', 'instructions', 'pull'],
                            cwd=project['path'],
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=30
                        )
                        # Don't fail if instructions pull fails, just log it
                        if instructions_result.returncode != 0:
                            logger.debug(f"Instructions pull failed for {project['name']}: {instructions_result.stderr}")
                    
                    # Step 2: Pull all other files
                    pull_result = subprocess.run(
                        ['csync', 'pull'],
                        cwd=project['path'],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',  # Handle unicode properly
                        errors='replace',   # Replace invalid chars instead of failing
                        timeout=120
                    )
                    
                    if pull_result.returncode != 0 and "No remote files" not in pull_result.stderr:
                        # Don't fail on unicode errors
                        error_msg = pull_result.stderr.strip() or 'Unknown error'
                        if 'UnicodeEncodeError' not in error_msg:
                            return {
                                'project': project['name'],
                                'path': project['path'],
                                'status': 'failed',
                                'message': f"Pull failed: {error_msg}",
                                'duration': time.time() - start_time
                            }
                    
                    # Step 3: Push all files (including instructions if modified)
                    cmd.append('push')
            
            # Run main sync command
            result = subprocess.run(
                cmd,
                cwd=project['path'],
                capture_output=True,
                text=True,
                encoding='utf-8',  # Handle unicode properly
                errors='replace',   # Replace invalid chars instead of failing
                timeout=300  # 5 minute timeout
            )
            
            # Reset config if changed
            for config_cmd in config_cmds:
                if 'false' in config_cmd:
                    reset_cmd = config_cmd[:-1] + ['true']
                else:
                    reset_cmd = config_cmd[:-1] + ['false']
                subprocess.run(reset_cmd, cwd=project['path'], capture_output=True, text=True,
                              encoding='utf-8', errors='replace')
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                details = ''
                if sync_options.get('with_instructions'):
                    details = '(with instructions)'
                
                return {
                    'project': project['name'],
                    'path': project['path'],
                    'status': 'success',
                    'message': 'Synced successfully',
                    'details': details,
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
    
    def start_watchers(self, projects: List[Dict]) -> List[Dict]:
        """Start file watchers for projects."""
        results = []
        
        for project in projects:
            try:
                # Start watcher in daemon mode
                result = subprocess.run(
                    ['csync', 'watch', 'start', '--daemon'],
                    cwd=project['path'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=10
                )
                
                if result.returncode == 0:
                    results.append({
                        'project': project['name'],
                        'status': 'started'
                    })
                else:
                    results.append({
                        'project': project['name'],
                        'status': 'failed',
                        'message': result.stderr.strip()
                    })
            except Exception as e:
                results.append({
                    'project': project['name'],
                    'status': 'error',
                    'message': str(e)
                })
        
        return results
    
    def stop_watchers(self, projects: List[Dict]) -> List[Dict]:
        """Stop file watchers for projects."""
        results = []
        
        for project in projects:
            try:
                # Stop watcher
                result = subprocess.run(
                    ['csync', 'watch', 'stop'],
                    cwd=project['path'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=10
                )
                
                if result.returncode == 0 or "No daemon found" in result.stdout:
                    results.append({
                        'project': project['name'],
                        'status': 'stopped'
                    })
                else:
                    results.append({
                        'project': project['name'],
                        'status': 'failed',
                        'message': result.stderr.strip()
                    })
            except Exception as e:
                results.append({
                    'project': project['name'],
                    'status': 'error',
                    'message': str(e)
                })
        
        return results
    
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
                    cmd = ['csync', 'chat', 'pull'] + safety_args
                    result = subprocess.run(
                        cmd,
                        cwd=project['path'],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
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
