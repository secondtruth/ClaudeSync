#!/usr/bin/env python3
"""
Migrate existing ClaudeSync projects to global workspace config.
This creates a single .claudesync-workspace.json file to manage all projects.
"""

import os
import json
from pathlib import Path

def migrate_to_global_config(workspace_root=None, remove_old=False):
    """Migrate from individual .claudesync directories to global config."""
    
    workspace_root = workspace_root or os.getcwd()
    global_config_file = os.path.join(workspace_root, '.claudesync-workspace.json')
    
    # Initialize global config structure
    global_config = {
        'version': '3.0.0',
        'workspace_root': workspace_root,
        'global_settings': {
            'active_provider': 'claude.ai',
            'upload_delay': 0.5,
            'max_file_size': 32768,
            'compression_algorithm': 'none',
            'two_way_sync': True,
            'prune_remote_files': True,
            'conflict_strategy': 'prompt'
        },
        'projects': {}
    }
    
    # Find and migrate existing projects
    migrated = 0
    for root, dirs, files in os.walk(workspace_root):
        if '.claudesync' in dirs:
            config_file = os.path.join(root, '.claudesync', 'config.local.json')
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        local_config = json.load(f)
                    
                    project_id = local_config.get('active_project_id')
                    if project_id:
                        project_name = local_config.get('active_project_name', os.path.basename(root))
                        
                        # Add to global config
                        global_config['projects'][project_id] = {
                            'name': project_name,
                            'id': project_id,
                            'local_path': root,
                            'organization_id': local_config.get('active_organization_id'),
                            'enabled': True
                        }
                        
                        # Copy organization ID to global if not set
                        if not global_config['global_settings'].get('active_organization_id'):
                            org_id = local_config.get('active_organization_id')
                            if org_id:
                                global_config['global_settings']['active_organization_id'] = org_id
                        
                        print(f"  ✓ Migrated: {project_name}")
                        migrated += 1
                        
                        if remove_old:
                            import shutil
                            shutil.rmtree(os.path.join(root, '.claudesync'))
                            print(f"    Removed old .claudesync directory")
                
                except Exception as e:
                    print(f"  ✗ Failed to migrate {root}: {e}")
            
            # Don't descend into project directories
            dirs.clear()
    
    # Save global config
    if migrated > 0:
        with open(global_config_file, 'w', encoding='utf-8') as f:
            json.dump(global_config, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Migrated {migrated} project(s) to global config")
        print(f"  Config saved to: {global_config_file}")
    else:
        print("No projects found to migrate")
    
    return global_config_file, migrated

if __name__ == '__main__':
    import sys
    
    workspace = sys.argv[1] if len(sys.argv) > 1 else '/mnt/c/Users/jordans/Documents/Obsidian/ObsidianVault/AI/Projects'
    remove = '--remove-old' in sys.argv
    
    print(f"Migrating workspace: {workspace}")
    config_file, count = migrate_to_global_config(workspace, remove_old=remove)
    
    if count > 0:
        print(f"\nNext steps:")
        print(f"  1. Review the config: cat '{config_file}'")
        print(f"  2. Use 'csync workspace sync-all' to sync all projects")
        print(f"\nNote: ClaudeSync will use the global config when available.")
