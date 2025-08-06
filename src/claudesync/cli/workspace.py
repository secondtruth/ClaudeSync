import click
import json
import os
from pathlib import Path
from ..workspace_config import WorkspaceConfig
from ..workspace_manager import WorkspaceManager
from ..utils import handle_errors, validate_and_get_provider
from ..syncmanager import SyncManager
from ..configmanager import FileConfigManager

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
    click.echo(json.dumps(config_data, indent=2))

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
@click.pass_obj
@handle_errors
def discover(config, output_json):
    """Discover all ClaudeSync projects in workspace."""
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
    projects = manager.discover_projects()
    
    if output_json:
        click.echo(json.dumps(projects, indent=2))
    else:
        if not projects:
            click.echo("No ClaudeSync projects found.")
            if not ws_config.get_workspace_root():
                click.echo("Tip: Set a workspace root with 'csync workspace set-root <path>'")
        else:
            click.echo(f"Found {len(projects)} project(s):")
            for project in projects:
                click.echo(f"\n  {project['name']}")
                click.echo(f"    Path: {project['path']}")
                click.echo(f"    ID: {project['id']}")

@workspace.command()
@click.option('--sequential', is_flag=True, help='Sync projects one at a time')
@click.option('--dry-run', is_flag=True, help='Show detailed preview of changes')
@click.option('--verbose', is_flag=True, help='Show enhanced dry-run details')
@click.option('--no-prune', is_flag=True, help='Do not delete remote files missing locally')
@click.option('--two-way', is_flag=True, help='Enable two-way sync for all projects')
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
@click.pass_obj
@handle_errors
def sync_all(config, sequential, dry_run, verbose, no_prune, two_way, push_only, 
             pull_only, no_instructions, watch_after, conflict_strategy,
             project_filter, project_exclude, parallel_workers):
    """Sync all projects in the workspace with granular control."""
    
    # Validate conflicting options
    if push_only and pull_only:
        raise click.BadParameter("Cannot use both --push-only and --pull-only")
    
    ws_config = WorkspaceConfig()
    manager = WorkspaceManager(ws_config)
    
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
        'two_way_sync': two_way,
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
        click.echo(f"  Direction: {'Pull only' if pull_only else 'Push only' if push_only else 'Bidirectional' if two_way else 'Push (standard)'}")
        click.echo(f"  Prune remote: {'No' if no_prune else 'Yes'}")
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
            if stats['files_to_delete_local'] > 0 and two_way:
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
        if two_way and total_stats['files_to_delete_local'] > 0:
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
@click.pass_obj
@handle_errors
def chat_pull_all(config, dry_run, backup_existing):
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
        'backup_existing': backup_existing
    }
    
    results = manager.pull_all_chats(projects, safety_options)
    
    # Show results
    click.echo("\nChat Pull Results:")
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] in ['failed', 'error'])
    
    for result in results:
        if result['status'] == 'success':
            click.echo(f"  ✓ {result['project']}")
        else:
            click.echo(f"  ✗ {result['project']}: {result['message']}")
    
    click.echo(f"\nSummary: {success_count} succeeded, {failed_count} failed")

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
def list(config):
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
