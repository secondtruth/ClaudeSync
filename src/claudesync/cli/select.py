"""
Enhanced project selection and management for ClaudeSync.
Provides interactive multi-select, filtering, and bulk operations.
"""

import click
import os
import json
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
from ..utils import handle_errors, validate_and_get_provider
from ..workspace_manager import WorkspaceManager, ProjectInfo
from ..workspace_config import WorkspaceConfig
import logging

logger = logging.getLogger(__name__)


@click.group()
def select():
    """Interactive project selection and bulk operations."""
    pass


@select.command()
@click.option(
    "--filter", 
    "filter_pattern",
    help="Filter projects by name pattern (supports wildcards)"
)
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects"
)
@click.option(
    "--max-depth",
    default=3,
    help="Maximum depth to search for projects (default: 3)"
)
@click.option(
    "--status",
    type=click.Choice(['all', 'active', 'recent', 'modified']),
    default='all',
    help="Filter by project status"
)
@click.option(
    "--output",
    type=click.Choice(['table', 'json']),
    default='table',
    help="Output format (table or json)"
)
@handle_errors
def list(filter_pattern, search_path, max_depth, status, output):
    """List all available projects with filtering options."""
    
    # Get workspace config
    config = WorkspaceConfig()
    search_paths = list(search_path) if search_path else config.get_default_search_paths()
    
    click.echo("🔍 Discovering projects...")
    click.echo(f"📁 Searching in {len(search_paths)} directories")
    
    # Discover projects
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, max_depth)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        return
    
    # Apply filtering
    filtered_projects = _apply_filters(projects, filter_pattern, status)
    
    if not filtered_projects:
        click.echo(f"❌ No projects match the specified filters")
        return
    
    # Handle JSON output
    if output == 'json':
        project_data = []
        for project in filtered_projects:
            project_info = {
                'name': project.name,
                'path': project.path,
                'status': _get_project_status(project),
                'hasConflicts': _project_has_conflicts(project),
                'hasConfig': project.has_config,
                'hasChats': _project_has_chats(project)
            }
            project_data.append(project_info)
        click.echo(json.dumps(project_data, indent=2))
        return
    
    # Display projects in table format
    click.echo(f"\n📋 Found {len(filtered_projects)} projects:")
    click.echo("=" * 80)
    
    for i, project in enumerate(filtered_projects, 1):
        status_info = _get_project_status_info(project)
        click.echo(f"{i:2d}. 📁 {project.name}")
        click.echo(f"     📍 {project.path}")
        click.echo(f"     📊 {status_info}")
        click.echo("")
    
    # Show summary statistics
    _show_project_statistics(filtered_projects)


@select.command()
@click.option(
    "--filter", 
    "filter_pattern",
    help="Filter projects by name pattern"
)
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects"
)
@click.option(
    "--category", 
    help="File category to sync for selected projects"
)
@click.option(
    "--dry-run", 
    is_flag=True, 
    help="Preview sync without making changes"
)
@click.option(
    "--skip-conflicts", 
    is_flag=True, 
    help="Skip conflict detection during sync"
)
@handle_errors
def sync(filter_pattern, search_path, category, dry_run, skip_conflicts):
    """Interactively select and sync multiple projects."""
    
    # Discover projects
    projects = _discover_and_filter_projects(search_path, filter_pattern)
    if not projects:
        return
    
    # Interactive multi-select
    selected_projects = _interactive_multi_select(projects, "Select projects to sync:")
    
    if not selected_projects:
        click.echo("❌ No projects selected for sync")
        return
    
    # Confirm operation
    click.echo(f"\n🚀 Selected {len(selected_projects)} projects for sync:")
    for project in selected_projects:
        click.echo(f"  • {project.name}")
    
    if category:
        click.echo(f"📂 Category: {category}")
    
    if dry_run:
        click.echo("🔍 Dry-run mode: Preview only")
    
    if not click.confirm("\nProceed with sync?"):
        click.echo("❌ Sync operation cancelled")
        return
    
    # Perform sync
    _bulk_sync_projects(selected_projects, category, dry_run, skip_conflicts)


@select.command()
@click.option(
    "--filter", 
    "filter_pattern",
    help="Filter projects by name pattern"
)
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects"
)
@click.option(
    "--dry-run", 
    is_flag=True, 
    help="Preview chat pull without making changes"
)
@click.option(
    "--backup-existing", 
    is_flag=True, 
    help="Create backup of existing chat files"
)
@handle_errors
def chat_pull(filter_pattern, search_path, dry_run, backup_existing):
    """Interactively select and pull chats for multiple projects."""
    
    # Discover projects
    projects = _discover_and_filter_projects(search_path, filter_pattern)
    if not projects:
        return
    
    # Interactive multi-select
    selected_projects = _interactive_multi_select(projects, "Select projects to pull chats for:")
    
    if not selected_projects:
        click.echo("❌ No projects selected for chat pull")
        return
    
    # Confirm operation
    click.echo(f"\n💬 Selected {len(selected_projects)} projects for chat pull:")
    for project in selected_projects:
        click.echo(f"  • {project.name}")
    
    if dry_run:
        click.echo("🔍 Dry-run mode: Preview only")
    if backup_existing:
        click.echo("💾 Existing files will be backed up")
    
    if not click.confirm("\nProceed with chat pull?"):
        click.echo("❌ Chat pull operation cancelled")
        return
    
    # Perform chat pull
    _bulk_chat_pull_projects(selected_projects, dry_run, backup_existing)


@select.command()
@click.option(
    "--filter", 
    "filter_pattern",
    help="Filter projects by name pattern"
)
@click.option(
    "--search-path", 
    multiple=True,
    help="Directories to search for projects"
)
@handle_errors
def status(filter_pattern, search_path):
    """Show detailed status for multiple selected projects."""
    
    # Discover projects
    projects = _discover_and_filter_projects(search_path, filter_pattern)
    if not projects:
        return
    
    # Interactive multi-select
    selected_projects = _interactive_multi_select(projects, "Select projects to check status for:")
    
    if not selected_projects:
        click.echo("❌ No projects selected for status check")
        return
    
    # Show detailed status
    click.echo(f"\n📊 Status for {len(selected_projects)} projects:")
    click.echo("=" * 80)
    
    for project in selected_projects:
        _show_detailed_project_status(project)
        click.echo("")


@select.command()
@click.option(
    "--output", 
    type=click.Choice(['table', 'json', 'csv']),
    default='table',
    help="Output format for the report"
)
@click.option(
    "--save-to", 
    type=click.Path(),
    help="Save report to file"
)
@handle_errors
def overview(output, save_to):
    """Generate comprehensive overview of all projects."""
    
    # Get all projects
    config = WorkspaceConfig()
    search_paths = config.get_default_search_paths()
    
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, 3)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        return
    
    # Generate report
    report_data = _generate_project_report(projects)
    
    if output == 'table':
        _display_table_report(report_data)
    elif output == 'json':
        _display_json_report(report_data, save_to)
    elif output == 'csv':
        _display_csv_report(report_data, save_to)


# Helper functions

def _discover_and_filter_projects(search_path, filter_pattern):
    """Common function to discover and filter projects."""
    config = WorkspaceConfig()
    search_paths = list(search_path) if search_path else config.get_default_search_paths()
    
    click.echo("🔍 Discovering projects...")
    
    manager = WorkspaceManager()
    projects = manager.discover_projects(search_paths, 3)
    
    if not projects:
        click.echo("❌ No ClaudeSync projects found")
        return []
    
    # Apply filtering
    filtered_projects = _apply_filters(projects, filter_pattern, 'all')
    
    if not filtered_projects:
        click.echo(f"❌ No projects match the specified filters")
        return []
    
    return filtered_projects


def _apply_filters(projects: List[ProjectInfo], filter_pattern: str = None, status: str = 'all') -> List[ProjectInfo]:
    """Apply filtering to project list."""
    import fnmatch
    
    filtered = projects
    
    # Apply name pattern filter
    if filter_pattern:
        filtered = [p for p in filtered if fnmatch.fnmatch(p.name.lower(), filter_pattern.lower())]
    
    # Apply status filter  
    if status != 'all':
        # This is a placeholder - could be enhanced with actual status detection
        # For now, just return all projects
        pass
    
    return filtered


def _interactive_multi_select(projects: List[ProjectInfo], prompt: str) -> List[ProjectInfo]:
    """Interactive multi-select interface for projects."""
    
    if len(projects) == 1:
        click.echo(f"\n📋 Found 1 project: {projects[0].name}")
        if click.confirm("Select this project?"):
            return projects
        else:
            return []
    
    click.echo(f"\n{prompt}")
    click.echo("=" * 60)
    
    # Display projects with numbers
    for i, project in enumerate(projects, 1):
        click.echo(f"{i:2d}. 📁 {project.name}")
        click.echo(f"     📍 {project.path}")
    
    click.echo("\n💡 Selection options:")
    click.echo("  • Single: 1")
    click.echo("  • Multiple: 1,3,5")
    click.echo("  • Range: 1-5")
    click.echo("  • All: all")
    click.echo("  • None: none")
    
    while True:
        selection = click.prompt("\nEnter your selection", type=str, default="all")
        
        try:
            selected_indices = _parse_selection(selection, len(projects))
            selected_projects = [projects[i-1] for i in selected_indices]
            
            if selected_projects:
                click.echo(f"✅ Selected {len(selected_projects)} projects:")
                for project in selected_projects:
                    click.echo(f"  • {project.name}")
                
                if click.confirm("Confirm selection?"):
                    return selected_projects
            else:
                click.echo("❌ No projects selected")
                return []
                
        except ValueError as e:
            click.echo(f"❌ Invalid selection: {e}")
            click.echo("💡 Please try again with a valid format")


def _parse_selection(selection: str, max_count: int) -> List[int]:
    """Parse user selection string into list of indices."""
    selection = selection.strip().lower()
    
    if selection == "all":
        return list(range(1, max_count + 1))
    elif selection == "none":
        return []
    
    indices = set()
    
    for part in selection.split(','):
        part = part.strip()
        
        if '-' in part:
            # Range selection
            start, end = part.split('-', 1)
            start_idx = int(start.strip())
            end_idx = int(end.strip())
            
            if start_idx < 1 or end_idx > max_count or start_idx > end_idx:
                raise ValueError(f"Invalid range: {part}")
            
            indices.update(range(start_idx, end_idx + 1))
        else:
            # Single selection
            idx = int(part)
            if idx < 1 or idx > max_count:
                raise ValueError(f"Index {idx} out of range (1-{max_count})")
            indices.add(idx)
    
    return sorted(list(indices))


def _bulk_sync_projects(projects: List[ProjectInfo], category: str = None, 
                       dry_run: bool = False, skip_conflicts: bool = False):
    """Perform bulk sync operation on selected projects."""
    import subprocess
    
    click.echo(f"\n🚀 Starting bulk sync for {len(projects)} projects...")
    
    results = {}
    
    for i, project in enumerate(projects, 1):
        click.echo(f"\n📁 Syncing {i}/{len(projects)}: {project.name}")
        
        try:
            # Build command
            cmd = ["claudesync", "push"]
            
            if category:
                cmd.extend(["--category", category])
            if dry_run:
                cmd.append("--dry-run")
            if skip_conflicts:
                cmd.append("--skip-conflicts")
            
            # Execute sync
            result = subprocess.run(
                cmd,
                cwd=str(project.path),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                click.echo(f"✅ {project.name}: Sync successful")
                results[project.name] = True
            else:
                click.echo(f"❌ {project.name}: Sync failed")
                if result.stderr:
                    click.echo(f"   Error: {result.stderr.strip()}")
                results[project.name] = False
                
        except subprocess.TimeoutExpired:
            click.echo(f"⏱️ {project.name}: Sync timeout")
            results[project.name] = False
        except Exception as e:
            click.echo(f"❌ {project.name}: Error - {e}")
            results[project.name] = False
    
    # Show summary
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    click.echo(f"\n📊 Bulk Sync Summary:")
    click.echo(f"  ✅ Successful: {successful}")
    click.echo(f"  ❌ Failed: {failed}")
    click.echo(f"  📋 Total: {len(results)}")


def _bulk_chat_pull_projects(projects: List[ProjectInfo], dry_run: bool = False, 
                           backup_existing: bool = False):
    """Perform bulk chat pull operation on selected projects.""" 
    import subprocess
    
    click.echo(f"\n💬 Starting bulk chat pull for {len(projects)} projects...")
    
    results = {}
    
    for i, project in enumerate(projects, 1):
        click.echo(f"\n📁 Pulling chats {i}/{len(projects)}: {project.name}")
        
        try:
            # Build command
            cmd = ["claudesync", "chat", "pull"]
            
            if dry_run:
                cmd.append("--dry-run")
            if backup_existing:
                cmd.append("--backup-existing")
            cmd.append("--force")  # Skip individual confirmations in bulk mode
            
            # Execute chat pull
            result = subprocess.run(
                cmd,
                cwd=str(project.path),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                click.echo(f"✅ {project.name}: Chat pull successful")
                results[project.name] = True
            else:
                click.echo(f"❌ {project.name}: Chat pull failed")
                if result.stderr:
                    click.echo(f"   Error: {result.stderr.strip()}")
                results[project.name] = False
                
        except subprocess.TimeoutExpired:
            click.echo(f"⏱️ {project.name}: Chat pull timeout")
            results[project.name] = False
        except Exception as e:
            click.echo(f"❌ {project.name}: Error - {e}")
            results[project.name] = False
    
    # Show summary
    successful = sum(1 for success in results.values() if success)
    failed = len(results) - successful
    
    click.echo(f"\n📊 Bulk Chat Pull Summary:")
    click.echo(f"  ✅ Successful: {successful}")
    click.echo(f"  ❌ Failed: {failed}")
    click.echo(f"  📋 Total: {len(results)}")


def _get_project_status_info(project: ProjectInfo) -> str:
    """Get status information for a project."""
    try:
        # Check for recent modifications
        config_file = project.path / ".claudesync" / "config.local.json"
        if config_file.exists():
            import time
            mod_time = config_file.stat().st_mtime
            days_ago = (time.time() - mod_time) / (24 * 3600)
            
            if days_ago < 1:
                return "🟢 Active (modified today)"
            elif days_ago < 7:
                return f"🟡 Recent (modified {int(days_ago)} days ago)"
            else:
                return f"🔵 Older (modified {int(days_ago)} days ago)"
        else:
            return "❓ Unknown status"
            
    except Exception:
        return "❓ Status check failed"


def _show_project_statistics(projects: List[ProjectInfo]):
    """Show statistics about the project list."""
    click.echo("📊 Project Statistics:")
    click.echo(f"  📁 Total Projects: {len(projects)}")
    
    # Status breakdown
    status_counts = {"active": 0, "recent": 0, "older": 0, "unknown": 0}
    
    for project in projects:
        status = _get_project_status_info(project)
        if "Active" in status:
            status_counts["active"] += 1
        elif "Recent" in status:
            status_counts["recent"] += 1
        elif "Older" in status:
            status_counts["older"] += 1
        else:
            status_counts["unknown"] += 1
    
    click.echo(f"  🟢 Active: {status_counts['active']}")
    click.echo(f"  🟡 Recent: {status_counts['recent']}")
    click.echo(f"  🔵 Older: {status_counts['older']}")
    click.echo(f"  ❓ Unknown: {status_counts['unknown']}")


def _show_detailed_project_status(project: ProjectInfo):
    """Show detailed status for a single project."""
    click.echo(f"📁 {project.name}")
    click.echo(f"   📍 Path: {project.path}")
    click.echo(f"   📊 Status: {_get_project_status_info(project)}")
    
    # Check for various files
    project_files = {
        "Config": project.path / ".claudesync" / "config.local.json",
        "Instructions": project.path / "project-instructions.md",
        "Chats": project.path / "claude_chats",
        "Gitignore": project.path / ".gitignore",
        "Claudeignore": project.path / ".claudeignore"
    }
    
    click.echo("   📄 Files:")
    for name, path in project_files.items():
        if path.exists():
            click.echo(f"      ✅ {name}")
        else:
            click.echo(f"      ❌ {name}")


def _generate_project_report(projects: List[ProjectInfo]) -> Dict:
    """Generate comprehensive report data."""
    report = {
        "summary": {
            "total_projects": len(projects),
            "scan_date": str(datetime.now()),
        },
        "projects": []
    }
    
    for project in projects:
        project_data = {
            "name": project.name,
            "path": str(project.path),
            "status": _get_project_status_info(project),
        }
        
        # Check file existence
        checks = {
            "has_config": (project.path / ".claudesync" / "config.local.json").exists(),
            "has_instructions": (project.path / "project-instructions.md").exists(),
            "has_chats": (project.path / "claude_chats").exists(),
            "has_gitignore": (project.path / ".gitignore").exists(),
            "has_claudeignore": (project.path / ".claudeignore").exists(),
        }
        
        project_data.update(checks)
        report["projects"].append(project_data)
    
    return report


def _display_table_report(report_data: Dict):
    """Display report in table format."""
    click.echo("📊 ClaudeSync Projects Report")
    click.echo("=" * 80)
    click.echo(f"Total Projects: {report_data['summary']['total_projects']}")
    click.echo(f"Scan Date: {report_data['summary']['scan_date']}")
    click.echo("")
    
    # Table header
    click.echo(f"{'Project':<25} {'Status':<20} {'Files':<20}")
    click.echo("-" * 65)
    
    for project in report_data["projects"]:
        name = project["name"][:24]
        status = project["status"][:19]
        
        files = []
        if project["has_config"]: files.append("C")
        if project["has_instructions"]: files.append("I") 
        if project["has_chats"]: files.append("H")
        if project["has_gitignore"]: files.append("G")
        if project["has_claudeignore"]: files.append("L")
        
        files_str = "".join(files)[:19]
        click.echo(f"{name:<25} {status:<20} {files_str:<20}")
    
    click.echo("\nFile Legend: C=Config, I=Instructions, H=Chats, G=Gitignore, L=Claudeignore")


def _display_json_report(report_data: Dict, save_to: str = None):
    """Display report in JSON format."""
    import json
    
    json_output = json.dumps(report_data, indent=2)
    
    if save_to:
        with open(save_to, 'w') as f:
            f.write(json_output)
        click.echo(f"✅ Report saved to: {save_to}")
    else:
        click.echo(json_output)


def _display_csv_report(report_data: Dict, save_to: str = None):
    """Display report in CSV format."""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Name", "Path", "Status", "Has Config", "Has Instructions", 
        "Has Chats", "Has Gitignore", "Has Claudeignore"
    ])
    
    # Data rows
    for project in report_data["projects"]:
        writer.writerow([
            project["name"],
            project["path"],
            project["status"],
            project["has_config"],
            project["has_instructions"],
            project["has_chats"],
            project["has_gitignore"],
            project["has_claudeignore"]
        ])
    
    csv_output = output.getvalue()
    
    if save_to:
        with open(save_to, 'w') as f:
            f.write(csv_output)
        click.echo(f"✅ Report saved to: {save_to}")
    else:
        click.echo(csv_output)
