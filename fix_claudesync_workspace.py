#!/usr/bin/env python3
"""
Clean up ClaudeSync workspace issues:
1. Remove double .claudesync directories
2. Rename .projectinstructions to project-instructions.md
"""

import os
import shutil
import json
from pathlib import Path

def fix_workspace(workspace_root):
    """Fix common issues in ClaudeSync workspace."""
    workspace_root = Path(workspace_root).expanduser()
    
    if not workspace_root.exists():
        print(f"Workspace not found: {workspace_root}")
        return
    
    fixed_count = 0
    
    for project_dir in workspace_root.iterdir():
        if not project_dir.is_dir():
            continue
        
        print(f"\nChecking: {project_dir.name}")
        
        # Fix 1: Double .claudesync directories
        double_claudesync = project_dir / '.claudesync' / '.claudesync'
        if double_claudesync.exists():
            print(f"  Found double .claudesync directory")
            
            # Check if inner has config
            inner_config = double_claudesync / 'config.local.json'
            outer_config = project_dir / '.claudesync' / 'config.local.json'
            
            if inner_config.exists() and not outer_config.exists():
                # Move config from inner to outer
                shutil.move(str(inner_config), str(outer_config))
                print(f"  Moved config to correct location")
            
            # Remove the inner .claudesync
            shutil.rmtree(double_claudesync)
            print(f"  Removed inner .claudesync directory")
            fixed_count += 1
        
        # Fix 2: Rename .projectinstructions to project-instructions.md
        old_instructions = project_dir / '.projectinstructions'
        new_instructions = project_dir / 'project-instructions.md'
        
        if old_instructions.exists() and not new_instructions.exists():
            shutil.move(str(old_instructions), str(new_instructions))
            print(f"  Renamed .projectinstructions to project-instructions.md")
            fixed_count += 1
        elif old_instructions.exists() and new_instructions.exists():
            # Both exist, remove the old one
            old_instructions.unlink()
            print(f"  Removed duplicate .projectinstructions")
            fixed_count += 1
        
        # Fix 3: Ensure config has correct local_path
        config_file = project_dir / '.claudesync' / 'config.local.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                if config.get('local_path') != str(project_dir):
                    config['local_path'] = str(project_dir)
                    with open(config_file, 'w') as f:
                        json.dump(config, f, indent=2)
                    print(f"  Fixed local_path in config")
                    fixed_count += 1
            except Exception as e:
                print(f"  Error reading config: {e}")
    
    print(f"\nFixed {fixed_count} issue(s)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fix_claudesync_workspace.py /path/to/workspace")
        sys.exit(1)
    
    fix_workspace(sys.argv[1])
