"""
ClaudeSync Configuration Healer

This module provides commands to fix and migrate existing configurations
to use the minimal dynamic configuration system.
"""

import click
import json
import os
import shutil
from pathlib import Path
import logging
from typing import List, Dict, Optional

from claudesync.configmanager.file_config_manager import FileConfigManager
from claudesync.dynamic_config import DynamicConfigManager
from claudesync.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)


@click.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
@click.option('--workspace', '-w', default=None, help='Workspace root directory')
@click.option('--backup/--no-backup', default=True, help='Backup existing configs')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')
@click.confirmation_option(prompt='This will modify all project configurations. Continue?')
def heal_all(workspace, backup, dry_run):
    """
    Fix all project configurations in the workspace.
    
    This command will:
    1. Find all projects with .claudesync directories
    2. Extract just the project_id from existing configs
    3. Create minimal new configs with only project_id
    4. Fix path mismatches
    5. Auto-discover project IDs for configs without them
    """
    click.echo("Starting configuration healing process...")
    
    # Determine workspace root
    if workspace:
        root_path = Path(workspace)
    else:
        # Try to auto-detect workspace
        root_path = Path.cwd()
        # Look for common workspace patterns
        if root_path.name == 'Projects' or 'Projects' in root_path.parts:
            click.echo(f"Using workspace: {root_path}")
        else:
            # Try to find Projects directory
            for parent in root_path.parents:
                projects_dir = parent / 'Projects'
                if projects_dir.exists():
                    root_path = projects_dir
                    click.echo(f"Found workspace: {root_path}")
                    break
    
    if not root_path.exists():
        click.echo(f"Error: Workspace not found: {root_path}", err=True)
        return
    
    # Initialize config and provider
    config = FileConfigManager()
    provider = ProviderFactory.get_provider(config)
    dynamic_config = DynamicConfigManager(config)
    
    # Find all projects
    projects = []
    for root, dirs, files in os.walk(root_path):
        if '.claudesync' in dirs:
            config_file = Path(root) / '.claudesync' / 'config.local.json'
            if config_file.exists():
                projects.append({
                    'path': Path(root),
                    'config_file': config_file
                })
            # Don't descend into project directories
            dirs.clear()
    
    click.echo(f"Found {len(projects)} projects to heal")
    
    fixed_count = 0
    error_count = 0
    
    for project_info in projects:
        project_path = project_info['path']
        config_file = project_info['config_file']
        project_name = project_path.name
        
        click.echo(f"\nProcessing: {project_name}")
        
        try:
            # Read existing config
            with open(config_file, 'r', encoding='utf-8') as f:
                old_config = json.load(f)
            
            # Backup if requested
            if backup and not dry_run:
                backup_file = config_file.with_suffix('.json.backup')
                shutil.copy2(config_file, backup_file)
                click.echo(f"  ✓ Backed up to {backup_file.name}")
            
            # Extract minimal config
            new_config = {}
            
            # Get project ID
            project_id = old_config.get('active_project_id')
            if project_id:
                new_config['active_project_id'] = project_id
            else:
                # Try to auto-discover
                click.echo(f"  ! No project_id found, attempting auto-discovery...")
                discovered_id = dynamic_config.auto_discover_project(str(project_path))
                if discovered_id:
                    new_config['active_project_id'] = discovered_id
                    click.echo(f"  ✓ Auto-discovered project ID: {discovered_id}")
                else:
                    click.echo(f"  ✗ Could not auto-discover project ID", err=True)
                    error_count += 1
                    continue
            
            # Check for issues
            issues = []
            
            # Check path mismatch
            old_path = old_config.get('local_path', '')
            expected_path = str(project_path).replace('\\', '/')
            if old_path and old_path != expected_path:
                issues.append(f"Path mismatch: {old_path} → {expected_path}")
            
            # Check name mismatch
            old_name = old_config.get('active_project_name', '')
            if old_name and old_name != project_name:
                # Only report if significantly different
                if old_name.replace('✨', '').strip() != project_name.replace('✨', '').strip():
                    issues.append(f"Name mismatch: {old_name} ≠ {project_name}")
            
            if issues:
                click.echo(f"  Issues found:")
                for issue in issues:
                    click.echo(f"    - {issue}")
            
            # Save minimal config
            if not dry_run:
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)
                click.echo(f"  ✓ Healed configuration (minimal)")
            else:
                click.echo(f"  [DRY RUN] Would save minimal config with project_id: {new_config.get('active_project_id')}")
            
            fixed_count += 1
            
        except Exception as e:
            click.echo(f"  ✗ Error: {e}", err=True)
            error_count += 1
    
    # Summary
    click.echo(f"\n{'='*50}")
    click.echo(f"Healing complete!")
    click.echo(f"  ✓ Fixed: {fixed_count} projects")
    if error_count:
        click.echo(f"  ✗ Errors: {error_count} projects")
    
    if dry_run:
        click.echo(f"\n[DRY RUN] No changes were made. Remove --dry-run to apply changes.")
    else:
        click.echo(f"\nAll configurations have been converted to minimal format.")
        click.echo(f"Project names and paths will now be resolved dynamically.")


@config.command()
@click.argument('project_path', required=False)
def heal_one(project_path):
    """
    Fix configuration for a single project.
    """
    if not project_path:
        project_path = os.getcwd()
    
    project_path = Path(project_path)
    config_file = project_path / '.claudesync' / 'config.local.json'
    
    if not config_file.exists():
        click.echo(f"Error: No configuration found at {config_file}", err=True)
        return
    
    config = FileConfigManager()
    dynamic_config = DynamicConfigManager(config)
    
    if dynamic_config.heal_config(str(project_path)):
        click.echo(f"✓ Configuration healed for {project_path.name}")
    else:
        click.echo(f"✗ Failed to heal configuration", err=True)


@config.command()
def check():
    """
    Check current configuration and show what would be resolved dynamically.
    """
    config = FileConfigManager()
    dynamic_config = DynamicConfigManager(config)
    
    click.echo("Current Configuration:")
    click.echo("=" * 50)
    
    # Show stored values
    click.echo("\nStored values:")
    click.echo(f"  Project ID: {config.local_config.get('active_project_id', 'Not set')}")
    click.echo(f"  Project Name: {config.local_config.get('active_project_name', 'Not set')}")
    click.echo(f"  Local Path: {config.local_config.get('local_path', 'Not set')}")
    click.echo(f"  Organization ID: {config.local_config.get('active_organization_id', 'Not set')}")
    
    # Show dynamic values
    click.echo("\nDynamic values (resolved at runtime):")
    click.echo(f"  Project Name: {dynamic_config.get('active_project_name', 'Not set')}")
    click.echo(f"  Local Path: {dynamic_config.get('local_path', 'Not set')}")
    click.echo(f"  Organization ID: {dynamic_config.get('active_organization_id', 'Not set')}")
    
    # Check for auto-discovery
    folder_name = Path.cwd().name
    click.echo(f"\nAuto-discovery:")
    click.echo(f"  Current folder: {folder_name}")
    
    discovered_id = dynamic_config.auto_discover_project()
    if discovered_id:
        click.echo(f"  ✓ Can auto-discover project ID: {discovered_id}")
    else:
        click.echo(f"  ✗ Cannot auto-discover project")
