import click
import json
import os
import sys
from pathlib import Path
from ..workspace_config import WorkspaceConfig
from ..workspace_manager import WorkspaceManager
from ..utils import handle_errors, validate_and_get_provider
from ..syncmanager import SyncManager
from ..configmanager import FileConfigManager

# Fix Windows Unicode issues
if sys.platform == "win32":
    # Ensure UTF-8 encoding for Windows console
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    # Set environment variable for child processes
    os.environ['PYTHONIOENCODING'] = 'utf-8'

@click.group()
def workspace():
    """Manage workspace with multiple ClaudeSync projects."""
    pass

@workspace.command()
@click.argument('path', type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.pass_obj
@handle_errors
def set_root(config, path):
    """Set the workspace root directory."""
    ws_config = WorkspaceConfig()
    ws_config.set_workspace_root(path)
    click.echo(f"Workspace root set to: {os.path.abspath(path)}")
    
    # Discover projects
    manager = WorkspaceManager(ws_config)
    projects = manager.discover_projects()
    
    if projects:
        click.echo(f"\nFound {len(projects)} project(s):")
        for project in projects:
            click.echo(f"  - {project['name']} at {project['relative_path']}")
    else:
        click.echo("\nNo ClaudeSync projects found in workspace.")

@workspace.command()
@click.pass_obj
@handle_errors
def config(config):
    """Show workspace configuration."""
    ws_config = WorkspaceConfig()
    config_data = ws_config.get_config()
    
    click.echo("Workspace Configuration:")
    click.echo(json.dumps(config_data, indent=2, ensure_ascii=False))

@workspace.command()
@click.pass_obj
@handle_errors
def reset(config):
    """Reset workspace configuration to defaults."""
    if click.confirm("This will reset all workspace settings. Continue?"):
        ws_config = WorkspaceConfig()
        ws_config.reset()
        click.echo("Workspace configuration reset to defaults.")

@workspace.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.option('--show-remote', is_flag=True, help='Also show remote projects not cloned locally')
@click.pass_obj
@handle_errors
def discover(config, output_json, show_remote):
    """Discover all ClaudeSync projects in workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    remote_not_local = []
    
    # Check for remote projects if requested
    if show_remote:
        provider = validate_and_get_provider(config)
        organization_id = config.get('active_organization_id')
        
        if organization_id:
            try:
                remote_projects = provider.get_projects(organization_id, include_archived=False)
                local_project_ids = {p['id'] for p in projects if p.get('id')}
                remote_not_local = [p for p in remote_projects if p['id'] not in local_project_ids]
            except Exception as e:
                click.echo(f"Warning: Could not fetch remote projects: {str(e)}")
    
    if output_json:
        output = {
            'local': projects,
            'remote_only': [{'name': p['name'], 'id': p['id']} for p in remote_not_local] if show_remote else []
        }
        click.echo(json.dumps(output, indent=2, ensure_ascii=False))

# Consolidated clone command from workspace_clone.py and clone.py
@workspace.command()
@click.option('--dry-run', is_flag=True, help='Show what would be cloned without cloning')
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.option('--skip-existing', is_flag=True, help='Skip projects that already exist locally')
@click.option('--clean', is_flag=True, help='Remove empty directories before cloning')
@click.pass_obj
@handle_errors
def clone(config, dry_run, include_archived, skip_existing, clean):
    """Clone all remote Claude projects to workspace."""
    provider = validate_and_get_provider(config)
    
    # Get workspace root
    ws_config = WorkspaceConfig()
    workspace_root = ws_config.get_workspace_root()
    
    if not workspace_root:
        workspace_root = click.prompt("Enter workspace root directory", 
                                    default=os.path.expanduser("~/claude-projects"))
        ws_config.set_workspace_root(workspace_root)
    
    workspace_root = os.path.expanduser(workspace_root)
    
    if not dry_run and not os.path.exists(workspace_root):
        os.makedirs(workspace_root, exist_ok=True)
    
    click.echo(f"Workspace root: {workspace_root}")
    
    # Clean empty directories if requested
    if clean and not dry_run and os.path.exists(workspace_root):
        click.echo("\nCleaning empty directories...")
        for item in os.listdir(workspace_root):
            item_path = os.path.join(workspace_root, item)
            if os.path.isdir(item_path):
                claudesync_path = os.path.join(item_path, '.claudesync', 'config.local.json')
                if not os.path.exists(claudesync_path):
                    try:
                        if not os.listdir(item_path):
                            os.rmdir(item_path)
                            click.echo(f"  Removed empty: {item}")
                    except:
                        pass
    
    # Get organization
    org_id = config.get('active_organization_id')
    if not org_id:
        click.echo("No active organization. Run 'csync auth login' first.")
        return
    
    # List all projects
    click.echo("\nFetching remote projects...")
    projects = provider.get_projects(org_id, include_archived=include_archived)
    
    if not projects:
        click.echo("No projects found.")
        return
    
    click.echo(f"Found {len(projects)} project(s)")
    
    # Process each project
    cloned = 0
    skipped = 0
    failed = 0
    
    for project in projects:
        project_name = project['name']
        project_id = project['id']
        is_archived = project.get('archived_at') is not None
        
        # Sanitize project name for filesystem (keep emojis)
        invalid_chars = '<>:"/\\|?*'
        safe_name = "".join(c if c not in invalid_chars else '_' 
                           for c in project_name).strip()
        safe_name = safe_name.rstrip('. ')
        project_path = os.path.join(workspace_root, safe_name)
        
        # Check if already exists
        claudesync_config = os.path.join(project_path, '.claudesync', 'config.local.json')
        
        if os.path.exists(project_path) and os.path.exists(claudesync_config):
            if skip_existing:
                click.echo(f"[SKIP] {project_name} - already exists")
                skipped += 1
                continue
        
        if dry_run:
            status = "[ARCHIVED]" if is_archived else "[ACTIVE]"
            click.echo(f"[DRY RUN] Would clone {status} {project_name} -> {project_path}")
            continue
        
        # Create project directory
        try:
            click.echo(f"\nCloning: {project_name}")
            os.makedirs(project_path, exist_ok=True)
            
            # Change to project directory
            original_cwd = os.getcwd()
            os.chdir(project_path)
            
            # Create local config
            local_config = FileConfigManager()
            local_config.set('local_path', project_path, local=True)
            local_config.set('active_provider', config.get('active_provider'), local=True)
            local_config.set('active_organization_id', org_id, local=True)
            local_config.set('active_project_id', project_id, local=True)
            local_config.set('active_project_name', project_name, local=True)
            local_config.set('two_way_sync', True, local=True)
            local_config.set('prune_remote_files', False, local=True)
            
            os.chdir(original_cwd)
            
            # Get remote files
            click.echo("  Fetching files...")
            remote_files = provider.list_files(org_id, project_id)
            
            # Download each file
            downloaded = 0
            for remote_file in remote_files:
                file_name = remote_file['file_name']
                if file_name == '.projectinstructions':
                    file_name = 'project-instructions.md'
                
                file_path = os.path.join(project_path, file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(remote_file.get('content', ''))
                
                downloaded += 1
            
            click.echo(f"  ✓ Cloned {downloaded} files")
            cloned += 1
            
        except Exception as e:
            click.echo(f"  ✗ Failed: {str(e)}")
            failed += 1
    
    if not dry_run:
        click.echo(f"\nSummary:")
        click.echo(f"  Cloned: {cloned}")
        click.echo(f"  Skipped: {skipped}")
        click.echo(f"  Failed: {failed}")
        click.echo(f"\nWorkspace root: {workspace_root}")

# Consolidated list command from workspace_clone.py
@workspace.command(name='list')
@click.option('--format', type=click.Choice(['table', 'json', 'simple']), 
              default='table', help='Output format')
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.pass_obj
@handle_errors
def list_remote(config, format, include_archived):
    """List all remote Claude projects."""
    provider = validate_and_get_provider(config)
    
    org_id = config.get('active_organization_id')
    if not org_id:
        click.echo("No active organization. Run 'csync auth login' first.")
        return
    
    projects = provider.get_projects(org_id, include_archived=include_archived)
    
    if not projects:
        click.echo("No projects found.")
        return
    
    if format == 'json':
        click.echo(json.dumps(projects, indent=2))
    elif format == 'simple':
        for project in projects:
            click.echo(project['id'])
    else:  # table format
        click.echo(f"\nRemote Projects ({len(projects)} total):")
        click.echo("=" * 80)
        
        for project in projects:
            status = "[ARCHIVED]" if project.get('archived_at') else "[ACTIVE]  "
            click.echo(f"{status} {project['name']}")
            click.echo(f"         ID: {project['id']}")
            if project.get('description'):
                click.echo(f"         Description: {project['description']}")
            click.echo()

# Workspace synchronization commands continue below...
        else:
            if projects:
                click.echo(f"Found {len(projects)} local project(s):")
                for project in projects:
                    click.echo(f"\n  📁 {project['name']}")
                    click.echo(f"     Path: {project['path']}")
                    click.echo(f"     ID: {project['id']}")
            
            if remote_not_local:
                click.echo(f"\nFound {len(remote_not_local)} remote project(s) not cloned locally:")
                for project in remote_not_local[:10]:  # Show first 10
                    click.echo(f"  ☁️  {project['name']}")
                if len(remote_not_local) > 10:
                    click.echo(f"  ... and {len(remote_not_local) - 10} more")
                click.echo("\nTip: Run 'csync workspace sync-all' to clone these projects")

@workspace.command()
@click.option('--sequential', is_flag=True, help='Sync projects one at a time')
@click.option('--dry-run', is_flag=True, help='Show detailed preview of changes')
@click.option('--verbose', is_flag=True, help='Show enhanced dry-run details')
@click.option('--no-prune', is_flag=True, help='Do not delete remote files missing locally')
@click.option('--no-prune-local', is_flag=True, help='Do not delete local files missing remotely') 
@click.option('--one-way', is_flag=True, help='Use one-way sync (push only, like old behavior)')
@click.option('--push-only', is_flag=True, help='Only push local changes (no pull)')
@click.option('--pull-only', is_flag=True, help='Only pull remote changes (no push)')
@click.option('--no-instructions', is_flag=True, help='Skip syncing project instructions files')
@click.option('--watch-after', is_flag=True, help='Start file watchers after sync')
@click.option('--conflict-strategy', 
              type=click.Choice(['prompt', 'local-wins', 'remote-wins']), 
              default='prompt',
              help='How to handle conflicts')
@click.option('--filter', 'project_filter', help='Only sync projects matching pattern')
@click.option('--exclude', 'project_exclude', help='Skip projects matching pattern')
@click.option('--parallel-workers', type=int, default=4, help='Number of parallel workers')
@click.option('--local-only', is_flag=True, help='Skip checking for new remote projects')
@click.pass_obj
@handle_errors
def sync_all(config, sequential, dry_run, verbose, no_prune, no_prune_local, one_way, push_only, 
             pull_only, no_instructions, watch_after, conflict_strategy,
             project_filter, project_exclude, parallel_workers, local_only):
    """Sync all projects in workspace (TRUE bidirectional sync by default).
    
    By default, performs true bidirectional sync:
    - Uploads new local files
    - Downloads new remote files  
    - Deletes local files that don't exist remotely
    - Deletes remote files that don't exist locally
    
    Use --one-way for old behavior (push only, no local deletions).
    Use --no-prune to keep remote files that don't exist locally.
    Use --no-prune-local to keep local files that don't exist remotely.
    """
    
    # Validate conflicting options
    if push_only and pull_only:
        raise click.BadParameter("Cannot use both --push-only and --pull-only")
    
    if one_way and (push_only or pull_only):
        raise click.BadParameter("Cannot use --one-way with --push-only or --pull-only")
    
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    # Check for new remote projects first (unless local-only)
    if not local_only and not push_only:
        provider = validate_and_get_provider(config)
        organization_id = config.get('active_organization_id')
        
        if organization_id:
            try:
                remote_projects = provider.get_projects(organization_id, include_archived=False)
                local_projects = manager.discover_projects()
                local_project_ids = {p['id'] for p in local_projects if p.get('id')}
                
                new_remote_projects = [p for p in remote_projects if p['id'] not in local_project_ids]
                
                if new_remote_projects:
                    click.echo(f"Found {len(new_remote_projects)} new remote project(s) to clone:")
                    for project in new_remote_projects[:5]:  # Show first 5
                        click.echo(f"  • {project['name']}")
                    if len(new_remote_projects) > 5:
                        click.echo(f"  ... and {len(new_remote_projects) - 5} more")
                    
                    if not dry_run and click.confirm("\nClone new remote projects before syncing?"):
                        # Initialize global workspace config
                        from claudesync.global_workspace_config import GlobalWorkspaceConfig
                        global_config = GlobalWorkspaceConfig(ws_config.get_workspace_root() or os.getcwd())
                        
                        # Clone the new projects
                        workspace_root = ws_config.get_workspace_root() or os.getcwd()
                        cloned = 0
                        
                        for project in new_remote_projects:
                            project_name = project['name']
                            project_id = project['id']
                            
                            # Sanitize project name for filesystem
                            invalid_chars = '<>:"/\\|?*'
                            safe_name = "".join(c if c not in invalid_chars else '_' for c in project_name).strip()
                            project_path = os.path.join(workspace_root, safe_name)
                            
                            if not os.path.exists(project_path):
                                try:
                                    os.makedirs(project_path, exist_ok=True)
                                    
                                    # Add to global workspace config instead of creating .claudesync
                                    global_config.add_project(
                                        project_name=project_name,
                                        project_id=project_id,
                                        local_path=project_path,
                                        organization_id=organization_id
                                    )
                                    
                                    click.echo(f"  ✓ Cloned: {project_name}")
                                    
                                    # Pull files from remote
                                    try:
                                        remote_files = provider.list_files(organization_id, project_id)
                                        if remote_files:
                                            click.echo(f"    Pulling {len(remote_files)} file(s)...")
                                            for remote_file in remote_files:
                                                file_name = remote_file['file_name']
                                                # Handle special project instructions file
                                                if file_name == '.projectinstructions':
                                                    file_name = 'project-instructions.md'
                                                
                                                file_path = os.path.join(project_path, file_name)
                                                # Create directory if needed
                                                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                                                
                                                # Get content from the remote_file directly
                                                content = remote_file.get('content', '')
                                                with open(file_path, 'w', encoding='utf-8') as f:
                                                    f.write(content)
                                            click.echo(f"    ✓ Files pulled successfully")
                                    except Exception as pull_error:
                                        click.echo(f"    ⚠️  Could not pull files: {str(pull_error)}")
                                    
                                    cloned += 1
                                except Exception as e:
                                    click.echo(f"  ✗ Failed to clone {project_name}: {str(e)}")
                        
                        if cloned > 0:
                            click.echo(f"Cloned {cloned} new project(s)\n")
            except Exception as e:
                click.echo(f"Warning: Could not check for remote projects: {str(e)}")
    
    projects = manager.discover_projects()
    
    # Apply filters
    if project_filter:
        projects = [p for p in projects if project_filter.lower() in p['name'].lower()]
    if project_exclude:
        projects = [p for p in projects if project_exclude.lower() not in p['name'].lower()]
    
    if not projects:
        click.echo("No projects found to sync.")
        return
    
    # Prepare sync options
    sync_options = {
        'prune_remote': not no_prune,
        'prune_local': not no_prune_local,  # New option for local pruning
        'two_way_sync': not one_way,  # Default to true unless --one-way is specified
        'push_only': push_only,
        'pull_only': pull_only,
        'with_instructions': not no_instructions,  # Inverted - default is True
        'conflict_strategy': conflict_strategy,
        'parallel_workers': parallel_workers if not sequential else 1
    }
    
    click.echo(f"Found {len(projects)} project(s) to sync.")
    
    # Show configuration
    if verbose or dry_run:
        click.echo("\nSync Configuration:")
        sync_mode = 'Pull only' if pull_only else 'Push only' if push_only else 'One-way push' if one_way else 'True bidirectional'
        click.echo(f"  Mode: {sync_mode}")
        if not one_way and not push_only and not pull_only:
            click.echo(f"  Delete remote files not in local: {'No' if no_prune else 'Yes'}")
            click.echo(f"  Delete local files not in remote: {'No' if no_prune_local else 'Yes'}")
        elif not pull_only:
            click.echo(f"  Delete remote files not in local: {'No' if no_prune else 'Yes'}")
        click.echo(f"  Instructions: {'Skip' if no_instructions else 'Include'}")
        click.echo(f"  Conflicts: {conflict_strategy}")
        click.echo(f"  Parallelism: {sync_options['parallel_workers']} workers")
        if watch_after:
            click.echo(f"  Post-sync: Start file watchers")
    
    if dry_run:
        # Enhanced dry-run with detailed information
        click.echo("\n" + "="*60)
        click.echo("DRY RUN - Analyzing changes...")
        click.echo("="*60)
        
        total_stats = {
            'files_to_push': 0,
            'files_to_pull': 0,
            'files_to_delete_remote': 0,
            'files_to_delete_local': 0,
            'instructions_to_update': 0,
            'conflicts_detected': 0
        }
        
        for project in projects:
            click.echo(f"\n📁 {project['name']} ({project['relative_path']})")
            
            # Analyze project
            stats = manager.analyze_project_changes(project, sync_options)
            
            # Show project stats
            if stats['files_to_push'] > 0:
                click.echo(f"  ↑ Files to upload: {stats['files_to_push']}")
            if stats['files_to_pull'] > 0:
                click.echo(f"  ↓ Files to download: {stats['files_to_pull']}")
            if stats['files_to_delete_remote'] > 0 and not no_prune:
                click.echo(f"  🗑️  Remote files to delete: {stats['files_to_delete_remote']}")
            if stats['files_to_delete_local'] > 0 and not no_prune_local and not one_way:
                click.echo(f"  🗑️  Local files to delete: {stats['files_to_delete_local']}")
            if stats['instructions_status']:
                click.echo(f"  📝 Instructions: {stats['instructions_status']}")
            if stats['conflicts_detected'] > 0:
                click.echo(f"  ⚠️  Conflicts detected: {stats['conflicts_detected']}")
            
            # Update totals
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
        
        # Show summary
        click.echo("\n" + "="*60)
        click.echo("SUMMARY")
        click.echo("="*60)
        click.echo(f"Total projects: {len(projects)}")
        click.echo(f"Total files to upload: {total_stats['files_to_push']}")
        click.echo(f"Total files to download: {total_stats['files_to_pull']}")
        if not no_prune and total_stats['files_to_delete_remote'] > 0:
            click.echo(f"Total remote files to delete: {total_stats['files_to_delete_remote']}")
        if not one_way and not no_prune_local and total_stats['files_to_delete_local'] > 0:
            click.echo(f"Total local files to delete: {total_stats['files_to_delete_local']}")
        if not no_instructions:
            click.echo(f"Instructions to update: {total_stats['instructions_to_update']}")
        if total_stats['conflicts_detected'] > 0:
            click.echo(f"⚠️  Total conflicts: {total_stats['conflicts_detected']}")
        
        return
    
    if not click.confirm("\nContinue with sync?"):
        return
    
    # Perform sync
    results = manager.sync_all_projects(
        projects,
        sync_options=sync_options,
        parallel=not sequential,
        dry_run=False
    )
    
    # Show results
    click.echo("\nSync Results:")
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] in ['failed', 'error', 'timeout'])
    
    for result in results:
        if result['status'] == 'success':
            details = result.get('details', '')
            click.echo(f"  ✓ {result['project']} ({result['duration']:.1f}s) {details}")
        else:
            click.echo(f"  ✗ {result['project']}: {result['message']}")
    
    click.echo(f"\nSummary: {success_count} succeeded, {failed_count} failed")
    
    # Start watchers if requested
    if watch_after and success_count > 0:
        click.echo("\nStarting file watchers...")
        watch_results = manager.start_watchers(
            [p for p in projects if any(r['project'] == p['name'] and r['status'] == 'success' for r in results)]
        )
        watch_success = sum(1 for r in watch_results if r['status'] == 'started')
        click.echo(f"Started {watch_success} watcher(s)")

@workspace.command()
@click.option('--dry-run', is_flag=True, help='Preview what will be downloaded')
@click.option('--backup-existing', is_flag=True, help='Backup existing chat files')
@click.option('--skip-errors', is_flag=True, help='Continue even if some projects fail')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed progress')
@click.pass_obj
@handle_errors
def chat_pull_all(config, dry_run, backup_existing, skip_errors, verbose):
    """Pull chats for all projects in workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if not projects:
        click.echo("No projects found.")
        return
    
    click.echo(f"Found {len(projects)} project(s).")
    
    if not dry_run and not click.confirm("Pull chats for all projects?"):
        return
    
    # Pull chats
    safety_options = {
        'dry_run': dry_run,
        'backup_existing': backup_existing,
        'skip_errors': skip_errors,
        'verbose': verbose
    }
    
    click.echo("\nStarting chat pull process...")
    results = manager.pull_all_chats(projects, safety_options)
    
    # Show final summary
    click.echo("\n" + "="*60)
    click.echo("Chat Pull Summary:")
    click.echo("="*60)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] in ['failed', 'error'])
    
    if verbose or failed_count > 0:
        for result in results:
            if result['status'] == 'success':
                click.echo(f"  ✓ {result['project']}")
            else:
                click.echo(f"  ✗ {result['project']}: {result['message'][:100]}")
    
    click.echo(f"\nTotal: {success_count} succeeded, {failed_count} failed out of {len(projects)} projects")

@workspace.command()
@click.pass_obj
@handle_errors
def status(config):
    """Show workspace status overview."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    status = manager.get_status()
    
    click.echo(f"Workspace Status")
    click.echo(f"================")
    click.echo(f"Root: {status['workspace_root']}")
    click.echo(f"Projects: {status['total_projects']}")
    
    if status['projects']:
        click.echo("\nProject Details:")
        for project in status['projects']:
            watcher_icon = "👁️ " if project['watcher'] == 'running' else "  "
            click.echo(f"  {watcher_icon}{project['name']}")
            click.echo(f"     Path: {project['path']}")
            click.echo(f"     Watcher: {project['watcher']}")

@workspace.command()
@click.option('--output-dir', help='Output directory for cloned projects')
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.option('--filter', 'name_filter', help='Only clone projects matching pattern')
@click.option('--skip-existing', is_flag=True, help='Skip projects that already exist locally')
@click.option('--dry-run', is_flag=True, help='Show what would be cloned without doing it')
@click.pass_obj
@handle_errors
def clone(config, output_dir, include_archived, name_filter, skip_existing, dry_run):
    """Clone all remote Claude.ai projects to local workspace."""
    provider = validate_and_get_provider(config)
    organization_id = config.get('active_organization_id')
    
    if not organization_id:
        click.echo("No active organization. Run 'csync organization set' first.")
        return
    
    # Get all remote projects
    click.echo(f"Fetching projects from organization...")
    projects = provider.get_projects(organization_id, include_archived=include_archived)
    
    # Apply filter if specified
    if name_filter:
        original_count = len(projects)
        projects = [p for p in projects if name_filter.lower() in p['name'].lower()]
        click.echo(f"Filtered {original_count} projects to {len(projects)} matching '{name_filter}'")
    
    if not projects:
        click.echo("No projects found to clone.")
        return
    
    # Determine output directory
    if not output_dir:
        ws_config = WorkspaceConfig()
        output_dir = ws_config.get_workspace_root()
        if not output_dir:
            output_dir = os.getcwd()
    
    output_dir = os.path.abspath(output_dir)
    click.echo(f"\nClone destination: {output_dir}")
    
    if dry_run:
        click.echo("\nDRY RUN - Would clone the following projects:")
    else:
        click.echo(f"\nFound {len(projects)} project(s) to clone.")
    
    # Process each project
    cloned = 0
    skipped = 0
    failed = 0
    
    for project in projects:
        project_name = project['name']
        project_id = project['id']
        is_archived = bool(project.get('archived_at'))
        
        # Sanitize project name for filesystem (keep emojis)
        invalid_chars = '<>:"/\\|?*'
        safe_name = "".join(c if c not in invalid_chars else '_' for c in project_name).strip()
        
        project_path = os.path.join(output_dir, safe_name)
        
        # Check if already exists
        if os.path.exists(project_path):
            if skip_existing:
                click.echo(f"  ⏭️  Skipping (exists): {project_name}")
                skipped += 1
                continue
            else:
                # Check if it's already a ClaudeSync project
                config_file = os.path.join(project_path, '.claudesync', 'config.local.json')
                if os.path.exists(config_file):
                    click.echo(f"  ⏭️  Skipping (already configured): {project_name}")
                    skipped += 1
                    continue
        
        if dry_run:
            status_icon = "🗄️" if is_archived else "📁"
            click.echo(f"  {status_icon} Would clone: {project_name} -> {project_path}")
            cloned += 1
        else:
            try:
                # Create directory
                os.makedirs(project_path, exist_ok=True)
                
                # Create .claudesync config directory
                claudesync_dir = os.path.join(project_path, '.claudesync')
                os.makedirs(claudesync_dir, exist_ok=True)
                
                # Create local config
                local_config = {
                    "active_provider": "claude.ai",
                    "local_path": project_path,
                    "active_organization_id": organization_id,
                    "active_project_id": project_id,
                    "active_project_name": project_name
                }
                
                config_file = os.path.join(claudesync_dir, 'config.local.json')
                with open(config_file, 'w') as f:
                    json.dump(local_config, f, indent=2)
                
                status_icon = "🗄️" if is_archived else "✓"
                click.echo(f"  {status_icon} Cloned: {project_name}")
                cloned += 1
                
            except Exception as e:
                click.echo(f"  ✗ Failed to clone {project_name}: {str(e)}")
                failed += 1
    
    # Summary
    click.echo(f"\n{'DRY RUN ' if dry_run else ''}Summary:")
    click.echo(f"  Cloned: {cloned}")
    if skipped > 0:
        click.echo(f"  Skipped: {skipped}")
    if failed > 0:
        click.echo(f"  Failed: {failed}")
    
    if not dry_run and cloned > 0:
        click.echo(f"\nNext steps:")
        click.echo(f"  1. cd into each project directory")
        click.echo(f"  2. Run 'csync pull' to get files from Claude.ai")
        click.echo(f"  3. Or use 'csync workspace sync-all --pull-only' to pull all at once")

@workspace.command()
@click.option('--include-archived', is_flag=True, help='Include archived projects')
@click.option('--show-ids', is_flag=True, help='Show project IDs')
@click.pass_obj
@handle_errors
def list(config, include_archived, show_ids):
    """List all remote Claude.ai projects."""
    provider = validate_and_get_provider(config)
    organization_id = config.get('active_organization_id')
    
    if not organization_id:
        click.echo("No active organization. Run 'csync organization set' first.")
        return
    
    click.echo(f"Fetching projects from organization...")
    projects = provider.get_projects(organization_id, include_archived=include_archived)
    
    if not projects:
        click.echo("No projects found.")
        return
    
    # Separate active and archived
    active = [p for p in projects if not p.get('archived_at')]
    archived = [p for p in projects if p.get('archived_at')]
    
    if active:
        click.echo(f"\nActive Projects ({len(active)}):")
        for project in active:
            if show_ids:
                click.echo(f"  📁 {project['name']} (ID: {project['id']})")
            else:
                click.echo(f"  📁 {project['name']}")
    
    if archived and include_archived:
        click.echo(f"\nArchived Projects ({len(archived)}):")
        for project in archived:
            if show_ids:
                click.echo(f"  🗄️  {project['name']} (ID: {project['id']})")
            else:
                click.echo(f"  🗄️  {project['name']}")
    
    click.echo(f"\nTotal: {len(projects)} project(s)")

@workspace.command()
@click.option('--stop', is_flag=True, help='Stop all running watchers')
@click.option('--start', is_flag=True, help='Start watchers for all projects')
@click.pass_obj
@handle_errors
def watchers(config, stop, start):
    """Manage file watchers for all projects."""
    if not stop and not start:
        click.echo("Please specify --start or --stop")
        return
        
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if not projects:
        click.echo("No projects found.")
        return
    
    if stop:
        click.echo(f"Stopping watchers for {len(projects)} project(s)...")
        results = manager.stop_watchers(projects)
        stopped = sum(1 for r in results if r['status'] == 'stopped')
        click.echo(f"Stopped {stopped} watcher(s)")
    
    if start:
        click.echo(f"Starting watchers for {len(projects)} project(s)...")
        results = manager.start_watchers(projects)
        started = sum(1 for r in results if r['status'] == 'started')
        click.echo(f"Started {started} watcher(s)")

@workspace.command()
@click.option('--remove-old', is_flag=True, help='Remove old .claudesync directories after migration')
@click.option('--dry-run', is_flag=True, help='Preview migration without making changes')
@click.pass_obj
@handle_errors
def migrate(config, remove_old, dry_run):
    """Migrate from individual .claudesync directories to global workspace config."""
    from claudesync.global_workspace_config import GlobalWorkspaceConfig
    
    ws_config = WorkspaceConfig()
    workspace_root = ws_config.get_workspace_root() or os.getcwd()
    
    # Initialize global config
    global_config = GlobalWorkspaceConfig(workspace_root)
    
    # Set global organization and session if available
    if config.get('active_organization_id'):
        global_config.set_global_setting('active_organization_id', config.get('active_organization_id'))
    if config.get('session_key'):
        global_config.set_global_setting('session_key', config.get('session_key'))
    
    click.echo(f"Scanning {workspace_root} for projects to migrate...")
    
    if dry_run:
        click.echo("\nDRY RUN - No changes will be made")
    
    # Find and migrate projects
    projects_found = 0
    projects_migrated = 0
    
    for root, dirs, files in os.walk(workspace_root):
        if '.claudesync' in dirs:
            claudesync_dir = os.path.join(root, '.claudesync')
            config_file = os.path.join(claudesync_dir, 'config.local.json')
            
            if os.path.exists(config_file):
                projects_found += 1
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        local_config = json.load(f)
                    
                    project_name = local_config.get('active_project_name', os.path.basename(root))
                    project_id = local_config.get('active_project_id')
                    org_id = local_config.get('active_organization_id')
                    
                    click.echo(f"\n  Found: {project_name}")
                    click.echo(f"    Path: {root}")
                    click.echo(f"    ID: {project_id}")
                    
                    if project_id and not dry_run:
                        global_config.add_project(
                            project_name=project_name,
                            project_id=project_id,
                            local_path=root,
                            organization_id=org_id
                        )
                        projects_migrated += 1
                        click.echo(f"    ✓ Migrated to global config")
                        
                        if remove_old:
                            import shutil
                            shutil.rmtree(claudesync_dir)
                            click.echo(f"    ✓ Removed old .claudesync directory")
                    
                except Exception as e:
                    click.echo(f"    ✗ Failed to migrate: {str(e)}")
            
            # Don't descend into project directories
            dirs.clear()
    
    # Summary
    click.echo(f"\n{'='*60}")
    click.echo(f"Migration Summary:")
    click.echo(f"  Projects found: {projects_found}")
    if not dry_run:
        click.echo(f"  Projects migrated: {projects_migrated}")
        click.echo(f"  Global config saved to: {global_config.config_file}")
    else:
        click.echo(f"  Would migrate: {projects_found} project(s)")
        click.echo(f"  Would save to: {os.path.join(workspace_root, '.claudesync-workspace.json')}")
    
    if not dry_run and projects_migrated > 0:
        click.echo(f"\n✓ Migration complete! Your workspace now uses a single global config.")
        click.echo(f"  View config: cat '{global_config.config_file}'")
        click.echo(f"  All projects: csync workspace list")
