import click
import json
from ..utils import handle_errors, validate_and_get_provider
from ..conflict_resolver import ConflictResolver
from ..utils import get_local_files

@click.group()
def conflict():
    """Manage file conflicts between local and remote."""
    pass

@conflict.command()
@click.option('--json', 'output_json', is_flag=True, help='Output in JSON format')
@click.pass_obj
@handle_errors
def detect(config, output_json):
    """Detect conflicts between local and remote files."""
    provider = validate_and_get_provider(config, require_project=True)
    resolver = ConflictResolver(config)
    
    # Get files
    local_path = config.get('local_path')
    local_files = get_local_files(config, local_path)
    
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    remote_files = provider.list_files(organization_id, project_id)
    
    # Detect conflicts
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    if output_json:
        click.echo(json.dumps([{
            'file': c['file_name'],
            'local_modified': c['local_modified'].isoformat(),
            'remote_modified': c['remote_modified'].isoformat()
        } for c in conflicts], indent=2))
    else:
        if not conflicts:
            click.echo("No conflicts detected.")
        else:
            click.echo(f"Found {len(conflicts)} conflict(s):")
            for conflict in conflicts:
                click.echo(f"  - {conflict['file_name']}")
                click.echo(f"    Local:  {conflict['local_modified']}")
                click.echo(f"    Remote: {conflict['remote_modified']}")

@conflict.command()
@click.option('--auto-resolve', type=click.Choice(['local-wins', 'remote-wins']),
              help='Automatically resolve conflicts')
@click.option('--file', help='Resolve specific file only')
@click.pass_obj
@handle_errors
def resolve(config, auto_resolve, file):
    """Resolve conflicts between local and remote files."""
    provider = validate_and_get_provider(config, require_project=True)
    resolver = ConflictResolver(config)
    
    # Get files
    local_path = config.get('local_path')
    local_files = get_local_files(config, local_path)
    
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    remote_files = provider.list_files(organization_id, project_id)
    
    # Detect conflicts
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    
    if file:
        conflicts = [c for c in conflicts if c['file_name'] == file]
    
    if not conflicts:
        click.echo("No conflicts to resolve.")
        return
    
    # Resolve each conflict
    strategy = auto_resolve or 'prompt'
    resolved_count = 0
    
    for conflict in conflicts:
        click.echo(f"\nResolving: {conflict['file_name']}")
        
        try:
            resolved_content = resolver.resolve_conflict(conflict, strategy)
            
            if resolved_content is not None:
                # Write resolved content to local file
                with open(conflict['local_path'], 'w', encoding='utf-8') as f:
                    f.write(resolved_content)
                resolved_count += 1
                click.echo(f"✓ Resolved: {conflict['file_name']}")
            else:
                click.echo(f"⚠ Skipped: {conflict['file_name']}")
                
        except Exception as e:
            click.echo(f"✗ Error resolving {conflict['file_name']}: {str(e)}")
    
    click.echo(f"\nResolved {resolved_count} of {len(conflicts)} conflicts.")

@conflict.command()
@click.pass_obj
@handle_errors
def status(config):
    """Show conflict status for the current project."""
    provider = validate_and_get_provider(config, require_project=True)
    resolver = ConflictResolver(config)
    
    # Get files
    local_path = config.get('local_path')
    local_files = get_local_files(config, local_path)
    
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    remote_files = provider.list_files(organization_id, project_id)
    
    # Detect conflicts
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    summary = resolver.get_conflict_summary()
    
    click.echo(f"Project: {config.get('active_project_name')}")
    click.echo(f"Conflicts: {summary['total_conflicts']}")
    
    if summary['resolution_needed']:
        click.echo("\nFiles with conflicts:")
        for file in summary['files']:
            click.echo(f"  - {file}")
        click.echo("\nRun 'claudesync conflict resolve' to resolve conflicts.")

@conflict.command()
@click.argument('file')
@click.option('--mode', type=click.Choice(['unified', 'side-by-side']), 
              default='unified', help='Diff display mode')
@click.pass_obj
@handle_errors
def diff(config, file, mode):
    """Show detailed diff for a specific file."""
    provider = validate_and_get_provider(config, require_project=True)
    resolver = ConflictResolver(config)
    
    # Get files
    local_path = config.get('local_path')
    local_files = get_local_files(config, local_path)
    
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    remote_files = provider.list_files(organization_id, project_id)
    
    # Find specific conflict
    conflicts = resolver.detect_conflicts(local_files, remote_files)
    conflict = next((c for c in conflicts if c['file_name'] == file), None)
    
    if not conflict:
        click.echo(f"No conflict found for file: {file}")
        return
    
    # Show diff
    if mode == 'unified':
        resolver._show_diff(conflict)
    else:
        # Side-by-side diff
        import difflib
        diff = difflib.HtmlDiff()
        html = diff.make_file(
            conflict['remote_content'].splitlines(),
            conflict['local_content'].splitlines(),
            fromdesc='Remote',
            todesc='Local'
        )
        
        # Write to temp file and open in browser
        import tempfile
        import webbrowser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html)
            webbrowser.open(f.name)

@conflict.command()
@click.option('--strategy', type=click.Choice(['local-wins', 'remote-wins', 'prompt']),
              default='prompt', help='Default resolution strategy')
@click.pass_obj
@handle_errors
def configure(config, strategy):
    """Configure conflict resolution settings."""
    config.set('conflict_resolution_strategy', strategy, local=True)
    click.echo(f"Default conflict resolution strategy set to: {strategy}")

# Aliases for convenience
@conflict.command()
@click.pass_context
def scan(ctx):
    """Alias for 'conflict detect'."""
    ctx.invoke(detect)

@conflict.command()
@click.pass_context
def fix(ctx):
    """Alias for 'conflict resolve'."""
    ctx.invoke(resolve)