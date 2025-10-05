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
            'instructions_to_update': 0,
            'conflicts_detected': 0
        }
        
        try:
            # Change to project directory and get actual sync manager
            project_path = project['path']
            old_dir = os.getcwd()
            os.chdir(project_path)
            
            # Import here to avoid circular imports
            from claudesync.configmanager.file_config_manager import FileConfigManager
            from claudesync.provider_factory import get_provider
            from claudesync.syncmanager import SyncManager
            
            try:
                # Initialize config and provider
                config = FileConfigManager()
                
                # Get provider
                provider = get_provider(config, config.get('active_provider'))
                
                # Create sync manager
                sync_manager = SyncManager(provider, config, config.get('local_path'))
                
                # Get local files (using utils function, not sync_manager)
                from claudesync.utils import get_local_files
                local_files = get_local_files(config, config.get('local_path'))
                
                # Get remote files  
                org_id = config.get("active_organization_id")
                proj_id = config.get("active_project_id")
                remote_files = provider.list_files(org_id, proj_id) if provider and org_id and proj_id else []
                
                # Calculate actual changes
                from claudesync.utils import compute_md5_hash
                local_path = config.get('local_path')
                local_checksums = {f: compute_md5_hash(os.path.join(local_path, f)) for f in local_files}
                remote_checksums = {f['file_name']: f.get('file_hash', '') for f in remote_files}
                
                # Files to push (new or modified locally)
                for local_file in local_files:
                    remote_checksum = remote_checksums.get(local_file, None)
                    if remote_checksum is None or local_checksums[local_file] != remote_checksum:
                        stats['files_to_push'] += 1
                
                # Files to pull (new or modified remotely)
                for remote_file in remote_files:
                    file_name = remote_file['file_name']
                    local_checksum = local_checksums.get(file_name, None)
                    remote_checksum = remote_file.get('file_hash', '')
                    if local_checksum is None or local_checksum != remote_checksum:
                        stats['files_to_pull'] += 1
                
                # Files to delete
                if sync_options.get('prune_remote', True):
                    for remote_file in remote_files:
                        if remote_file['file_name'] not in local_files:
                            stats['files_to_delete_remote'] += 1
                
                if sync_options.get('prune_local', False) and not sync_options.get('one_way', True):
                    for local_file in local_files:
                        if local_file not in remote_checksums:
                            stats['files_to_delete_local'] += 1
                
                # Check for project instructions
                instructions_file = os.path.join(project_path, 'project-instructions.md')
                old_instructions_file = os.path.join(project_path, '.projectinstructions')
                
                if os.path.exists(instructions_file):
                    stats['instructions_status'] = 'Will update'
                    stats['instructions_to_update'] = 1
                elif os.path.exists(old_instructions_file):
                    stats['instructions_status'] = 'Will rename and update'
                    stats['instructions_to_update'] = 1
                elif sync_options.get('with_instructions'):
                    stats['instructions_status'] = 'Will create'
                    stats['instructions_to_update'] = 1
                
                # Detect conflicts (files modified both locally and remotely)
                for local_file in local_files:
                    if local_file in remote_checksums:
                        if (local_checksums[local_file] != remote_checksums[local_file] and
                            local_checksums[local_file] and remote_checksums[local_file]):
                            # Both have different non-empty checksums
                            stats['conflicts_detected'] += 1
                            
            finally:
                os.chdir(old_dir)
                
        except Exception as e:
            # If analysis fails, use estimates as fallback
            import click
            click.echo(f"  ⚠️  Could not analyze {project.get('name', 'Unknown')}: {str(e)}")
            
            # Basic file counting as fallback
            local_files = []
            for root, dirs, files in os.walk(project_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != 'node_modules']
                for file in files:
                    if not file.startswith('.'):
                        local_files.append(os.path.join(root, file))
            
            stats['files_to_push'] = len(local_files)
            
            # Use conservative estimates for other values
            if sync_options.get('pull_only'):
                stats['files_to_push'] = 0
                stats['files_to_pull'] = 5  # Estimate
            elif sync_options.get('push_only'):
                stats['files_to_pull'] = 0
            else:
                stats['files_to_pull'] = 2  # Estimate
            
            if sync_options.get('prune_remote', True):
                stats['files_to_delete_remote'] = 1  # Estimate
        
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
        """Sync a single project with TRUE bidirectional sync."""
        start_time = time.time()
        
        try:
            # Build command based on options
            cmd = ['csync']
            
            # Temporarily set config options if needed
            config_cmds = []
            
            if not sync_options.get('prune_remote', True):
                config_cmds.append(['csync', 'config', 'set', 'prune_remote_files', 'false'])
            
            if not sync_options.get('prune_local', True):
                config_cmds.append(['csync', 'config', 'set', 'prune_local_files', 'false'])
            
            # Always enable two_way_sync for true bidirectional sync unless one-way is requested
            if not sync_options.get('push_only') and not sync_options.get('pull_only'):
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
                # TRUE BIDIRECTIONAL SYNC - always use the sync command with two_way_sync enabled
                
                # Step 1: Sync project instructions first
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
                    # Don't fail if instructions sync fails, just log it
                    if instructions_result.returncode != 0:
                        logger.debug(f"Instructions sync failed for {project['name']}: {instructions_result.stderr}")
                
                # Step 2: Use the sync command for true bidirectional sync
                cmd.append('sync')
                cmd.extend(['--conflict-strategy', sync_options.get('conflict_strategy', 'prompt')])
                
                # Note: With two_way_sync enabled in config, the sync command will:
                # - Pull remote files that don't exist locally
                # - Push local files that don't exist remotely  
                # - Update files that differ (based on checksums)
                # - Delete local files that don't exist remotely
                # - Delete remote files that don't exist locally (if prune_remote is true)
            
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
                if 'prune_remote_files' in config_cmd:
                    reset_cmd = ['csync', 'config', 'set', 'prune_remote_files', 'true']
                elif 'prune_local_files' in config_cmd:
                    reset_cmd = ['csync', 'config', 'set', 'prune_local_files', 'true']
                elif 'two_way_sync' in config_cmd:
                    reset_cmd = ['csync', 'config', 'set', 'two_way_sync', 'false']
                else:
                    continue
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
        
        # Process projects with detailed feedback
        for idx, project in enumerate(projects, 1):
            project_name = project['name']
            click.echo(f"\n[{idx}/{len(projects)}] Processing: {project_name}")
            
            try:
                # Ensure path exists and is valid
                project_path = project['path']
                if not os.path.exists(project_path):
                    results.append({
                        'project': project_name,
                        'status': 'error',
                        'message': f'Project path does not exist: {project_path}'
                    })
                    continue
                
                # Check for .claudesync directory
                claudesync_dir = os.path.join(project_path, '.claudesync')
                if not os.path.exists(claudesync_dir):
                    results.append({
                        'project': project_name,
                        'status': 'error',
                        'message': 'No .claudesync directory found'
                    })
                    continue
                
                # Get current organization from global config
                from claudesync.configmanager.file_config_manager import FileConfigManager
                global_config = FileConfigManager()
                org_id = global_config.get("active_organization_id")
                
                # Build command with proper encoding and organization context
                cmd = ['csync', 'chat', 'pull'] + safety_args
                
                # Debug output
                click.echo(f"  Running: {' '.join(cmd)}")
                click.echo(f"  In directory: {project_path}")
                if org_id:
                    click.echo(f"  Using organization: {org_id[:8]}...")
                
                # Use shell=True on Windows for better path handling
                import platform
                use_shell = platform.system() == 'Windows'
                
                # Set environment variable to pass organization context
                env = os.environ.copy()
                if org_id:
                    env['CLAUDESYNC_ORG_ID'] = org_id
                
                # Run with shorter timeout and better error handling
                result = subprocess.run(
                    cmd,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=30,  # Reduced from 120 to 30 seconds
                    shell=use_shell,
                    env=env
                )
                
                if result.returncode == 0:
                    # Check if there's actual output
                    output = result.stdout.strip()
                    if output:
                        click.echo(f"  ✓ Success: {output[:100]}")  # Show first 100 chars
                    else:
                        click.echo(f"  ✓ Chats pulled successfully")
                    
                    results.append({
                        'project': project_name,
                        'status': 'success',
                        'message': 'Chats pulled successfully'
                    })
                else:
                    error_msg = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
                    click.echo(f"  ✗ Failed: {error_msg[:200]}")  # Show first 200 chars
                    
                    results.append({
                        'project': project_name,
                        'status': 'failed',
                        'message': error_msg
                    })
            
            except subprocess.TimeoutExpired:
                click.echo(f"  ✗ Timeout: Command took longer than 30 seconds")
                results.append({
                    'project': project_name,
                    'status': 'error',
                    'message': 'Command timed out after 30 seconds'
                })
            except Exception as e:
                click.echo(f"  ✗ Error: {str(e)}")
                results.append({
                    'project': project_name,
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
