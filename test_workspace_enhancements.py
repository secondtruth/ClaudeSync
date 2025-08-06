#!/usr/bin/env python3
"""
Test script for enhanced ClaudeSync workspace sync-all options
"""

import subprocess
import sys

def run_command(cmd):
    """Run a command and show output."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    
    return result.returncode

def main():
    """Test the new workspace sync-all options."""
    
    print("ClaudeSync Enhanced Workspace Commands Test")
    print("=" * 60)
    
    # Test 1: Show help for new options
    print("\n1. Show help for sync-all command:")
    run_command(['csync', 'workspace', 'sync-all', '--help'])
    
    # Test 2: Verbose dry-run
    print("\n2. Verbose dry-run (shows detailed changes):")
    run_command(['csync', 'workspace', 'sync-all', '--dry-run', '--verbose'])
    
    # Test 3: Pull only with no pruning
    print("\n3. Pull only without pruning remote files:")
    run_command(['csync', 'workspace', 'sync-all', '--pull-only', '--no-prune', '--dry-run'])
    
    # Test 4: Push with instructions
    print("\n4. Push with project instructions:")
    run_command(['csync', 'workspace', 'sync-all', '--push-only', '--with-instructions', '--dry-run'])
    
    # Test 5: Filter projects
    print("\n5. Sync only projects matching pattern:")
    run_command(['csync', 'workspace', 'sync-all', '--filter', 'test', '--dry-run'])
    
    # Test 6: Watcher management
    print("\n6. Show watcher status:")
    run_command(['csync', 'workspace', 'watchers', '--help'])
    
    print("\n" + "="*60)
    print("Test complete! New options available:")
    print("""
    Direction Control:
    --push-only         Only push local changes (no pull)
    --pull-only         Only pull remote changes (no push)
    --two-way          Enable bidirectional sync
    
    File Management:
    --no-prune         Don't delete remote files missing locally
    --with-instructions Sync project instructions files
    
    Conflict Handling:
    --conflict-strategy [prompt|local-wins|remote-wins]
    
    Filtering:
    --filter PATTERN   Only sync projects matching pattern
    --exclude PATTERN  Skip projects matching pattern
    
    Performance:
    --parallel-workers N  Number of parallel workers (default: 4)
    --sequential         Sync one at a time
    
    Post-Sync:
    --watch-after       Start file watchers after sync
    
    Output:
    --dry-run          Preview changes without syncing
    --verbose          Enhanced dry-run details
    
    Watcher Management:
    csync workspace watchers --start  Start all watchers
    csync workspace watchers --stop   Stop all watchers
    """)

if __name__ == '__main__':
    main()
