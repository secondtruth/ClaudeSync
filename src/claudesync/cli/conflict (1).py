"""
Conflict resolution CLI commands for ClaudeSync.
Handles detection and resolution of sync conflicts.
"""

import click
import os
from pathlib import Path
from ..utils import handle_errors, validate_and_get_provider, get_local_files
from ..conflict_resolver import ConflictResolver, ConflictResolution
import logging

logger = logging.getLogger(__name__)


@click.group()
def conflict():
    """Manage and resolve synchronization conflicts."""
    pass


@conflict.command()
@click.option(
    "--auto-resolve", 
    type=click.Choice(['local', 'remote', 'skip']),
    help="Automatically resolve conflicts using specified strategy"
)
@click.option(
    "--category", 
    help="Specify the file category to check for conflicts"
)
@click.option(
    "--count",
    is_flag=True,
    help="Only output the conflict count (for automation)"
)
@click.pass_obj
@handle_errors
def detect(config, auto_resolve, category, count):
    """Detect conflicts between local and remote files."""
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No local project path found. Please run from a project directory.")
        return
    
    # Get local and remote files
    click.echo("🔍 Scanning for conflicts...")
    local_files = get_local_files(config, local_path, category)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    # Detect conflicts
    resolver = ConflictResolver(config)
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    # If count flag is set, only output the count
    if count:
        click.echo(f"{len(conflicts)} conflicts")
        return
    
    if not conflicts:
        click.echo("✅ No conflicts detected. All files are in sync.")
        return
    
    click.echo(f"⚠️  Found {len(conflicts)} conflicts:")
    
    # Display conflicts
    for i, conflict in enumerate(conflicts, 1):
        local_size = len(conflict.local_content)
        remote_size = len(conflict.remote_content)
        click.echo(f"  {i}. 📄 {conflict.file_path}")
        click.echo(f"     Local: {local_size} chars | Remote: {remote_size} chars")
    
    click.echo("")
    
    # Handle auto-resolution
    if auto_resolve:
        resolution_map = {
            'local': ConflictResolution.KEEP_LOCAL,
            'remote': ConflictResolution.KEEP_REMOTE,
            'skip': ConflictResolution.SKIP
        }
        resolution = resolution_map[auto_resolve]
        
        click.echo(f"🤖 Auto-resolving all conflicts using '{auto_resolve}' strategy...")
        
        success_count = 0
        for conflict in conflicts:
            if resolver.apply_resolution(conflict, resolution):
                success_count += 1
                click.echo(f"✅ Resolved: {conflict.file_path}")
            else:
                click.echo(f"❌ Failed: {conflict.file_path}")
        
        click.echo(f"\n🎯 Resolved {success_count}/{len(conflicts)} conflicts")
        
    else:
        # Interactive resolution
        click.echo("💡 Use 'claudesync conflict resolve' for interactive resolution")
        click.echo("💡 Or use --auto-resolve flag with 'local', 'remote', or 'skip'")


@conflict.command()
@click.option(
    "--category", 
    help="Specify the file category to resolve conflicts for"
)
@click.option(
    "--file", 
    help="Resolve conflicts for a specific file only"
)
@click.pass_obj
@handle_errors  
def resolve(config, category, file):
    """Interactively resolve conflicts between local and remote files."""
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No local project path found. Please run from a project directory.")
        return
    
    # Get local and remote files
    click.echo("🔍 Scanning for conflicts...")
    local_files = get_local_files(config, local_path, category)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    # Detect conflicts
    resolver = ConflictResolver(config)
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    if not conflicts:
        click.echo("✅ No conflicts detected. All files are in sync.")
        return
    
    # Filter to specific file if requested
    if file:
        conflicts = [c for c in conflicts if c.file_path == file]
        if not conflicts:
            click.echo(f"❌ No conflicts found for file: {file}")
            return
    
    # Interactive resolution
    click.echo(f"🔧 Starting interactive conflict resolution for {len(conflicts)} files...")
    resolutions = resolver.resolve_all_conflicts(interactive=True)
    
    success_count = len(resolutions)
    click.echo(f"\n🎯 Successfully resolved {success_count}/{len(conflicts)} conflicts")
    
    if success_count > 0:
        click.echo("\n💡 Run 'claudesync push' to sync the resolved files")


@conflict.command()
@click.option(
    "--category", 
    help="Specify the file category to check"
)
@click.pass_obj
@handle_errors
def status(config, category):
    """Show conflict status for the current project."""
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    active_project_name = config.get("active_project_name")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No local project path found. Please run from a project directory.")
        return
    
    click.echo(f"📊 Conflict Status for Project: {active_project_name}")
    click.echo("=" * 60)
    
    # Get local and remote files
    local_files = get_local_files(config, local_path, category)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    click.echo(f"📁 Local files: {len(local_files)}")
    click.echo(f"☁️  Remote files: {len(remote_files)}")
    
    # Detect conflicts
    resolver = ConflictResolver(config)
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    if not conflicts:
        click.echo("✅ Status: All files in sync - no conflicts")
        return
    
    click.echo(f"⚠️  Conflicts: {len(conflicts)} files need attention")
    click.echo("")
    
    # Show conflict details
    for i, conflict in enumerate(conflicts, 1):
        local_size = len(conflict.local_content)
        remote_size = len(conflict.remote_content)
        size_diff = abs(local_size - remote_size)
        
        click.echo(f"  {i}. 📄 {conflict.file_path}")
        click.echo(f"     📊 Local: {local_size:,} chars | Remote: {remote_size:,} chars | Diff: {size_diff:,}")
        
        # Show a preview of changes
        diff_lines = conflict.get_diff()
        if diff_lines:
            added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
            click.echo(f"     🔀 Changes: +{added} lines, -{removed} lines")
        
        click.echo("")
    
    click.echo("💡 Use 'claudesync conflict resolve' to resolve these conflicts")


@conflict.command()
@click.argument("file_path")
@click.pass_obj
@handle_errors
def diff(config, file_path):
    """Show detailed diff for a conflicted file."""
    provider = validate_and_get_provider(config, require_project=True)
    
    active_organization_id = config.get("active_organization_id")
    active_project_id = config.get("active_project_id")
    local_path = config.get_local_path()
    
    if not local_path:
        click.echo("❌ No local project path found. Please run from a project directory.")
        return
    
    # Get local and remote files
    local_files = get_local_files(config, local_path)
    remote_files = provider.list_files(active_organization_id, active_project_id)
    
    # Find the specific file
    if file_path not in local_files:
        click.echo(f"❌ File not found in local files: {file_path}")
        return
    
    remote_file = next((rf for rf in remote_files if rf['file_name'] == file_path), None)
    if not remote_file:
        click.echo(f"❌ File not found in remote files: {file_path}")
        return
    
    # Create conflict info
    local_file_full_path = os.path.join(local_path, file_path)
    try:
        with open(local_file_full_path, 'r', encoding='utf-8') as f:
            local_content = f.read()
    except Exception as e:
        click.echo(f"❌ Error reading local file: {e}")
        return
    
    from ..conflict_resolver import ConflictInfo
    conflict = ConflictInfo(file_path, local_content, remote_file['content'])
    
    # Check if there's actually a conflict
    from ..utils import compute_md5_hash
    local_checksum = compute_md5_hash(local_content)
    remote_checksum = compute_md5_hash(remote_file['content'])
    
    if local_checksum == remote_checksum:
        click.echo(f"✅ No conflicts found for: {file_path}")
        click.echo("Files are identical")
        return
    
    # Show detailed diff
    click.echo(f"📄 Detailed diff for: {file_path}")
    click.echo("=" * 80)
    
    local_size = len(local_content)
    remote_size = len(remote_file['content'])
    click.echo(f"📁 Local:  {local_size:,} characters")
    click.echo(f"☁️  Remote: {remote_size:,} characters")
    click.echo("")
    
    # Unified diff
    diff_lines = conflict.get_diff()
    if diff_lines:
        click.echo("📋 Unified Diff:")
        click.echo("-" * 40)
        
        for line in diff_lines:
            if line.startswith('+') and not line.startswith('+++'):
                click.echo(click.style(line, fg='green'))
            elif line.startswith('-') and not line.startswith('---'):
                click.echo(click.style(line, fg='red'))
            elif line.startswith('@@'):
                click.echo(click.style(line, fg='cyan'))
            else:
                click.echo(line)
    else:
        click.echo("❓ No diff lines detected (possible encoding issue)")
    
    click.echo("")
    click.echo("💡 Use 'claudesync conflict resolve --file {}' to resolve this conflict".format(file_path))


@conflict.command()
@click.option(
    "--strategy",
    type=click.Choice(['local-wins', 'remote-wins', 'auto-merge']),
    default='local-wins',
    help="Default conflict resolution strategy"
)
@click.pass_obj
@handle_errors
def configure(config, strategy):
    """Configure default conflict resolution settings."""
    # Store conflict resolution preferences
    config.set("conflict_resolution_strategy", strategy, local=True)
    
    strategy_descriptions = {
        'local-wins': 'Local files take precedence over remote files',
        'remote-wins': 'Remote files take precedence over local files', 
        'auto-merge': 'Attempt automatic merging when possible'
    }
    
    click.echo(f"🔧 Conflict resolution strategy set to: {strategy}")
    click.echo(f"📝 Description: {strategy_descriptions[strategy]}")
    click.echo("")
    click.echo("💡 This setting affects auto-resolution behavior during sync")
    click.echo("💡 You can still resolve conflicts manually when needed")


# Add helpful aliases
@conflict.command()
@click.pass_context
def scan(ctx):
    """Alias for 'conflict detect' - scan for conflicts."""
    ctx.forward(detect)


@conflict.command() 
@click.pass_context
def fix(ctx):
    """Alias for 'conflict resolve' - fix conflicts interactively."""
    ctx.forward(resolve)
