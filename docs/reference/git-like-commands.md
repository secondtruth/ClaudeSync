# ClaudeSync Git-like Commands

## Overview
ClaudeSync now supports Git-like commands for more intuitive file synchronization with Claude.ai projects.

## Command Structure

### Push (Upload Only)
```bash
csync push [--dry-run]
```
- Uploads local files to Claude project
- Does NOT download remote files
- Use `--dry-run` to preview what will be uploaded

### Pull (Download Only)
```bash
csync pull [--dry-run] [--force] [--merge]
```
- Downloads files from Claude project to local
- Does NOT upload local files
- Options:
  - `--dry-run`: Preview what will be downloaded
  - `--force`: Overwrite local files without prompting
  - `--merge`: Detect and resolve conflicts interactively

### Sync (Bi-directional)
```bash
csync sync [--dry-run] [--no-pull] [--no-push] [--conflict-strategy=<strategy>]
```
- Full bi-directional synchronization
- Uploads local changes AND downloads remote changes
- Options:
  - `--dry-run`: Preview all changes
  - `--no-pull`: Skip downloading (push only)
  - `--no-push`: Skip uploading (pull only)
  - `--conflict-strategy`: How to handle conflicts (prompt/local-wins/remote-wins)

## Key Differences from Git

1. **No Staging Area**: Changes are synced directly
2. **No Commits**: Each sync is immediate
3. **Automatic Conflict Detection**: Built-in conflict resolution
4. **Project-Based**: Works with Claude.ai projects, not git repositories

## Configuration

### Two-way Sync Setting
```json
{
  "two_way_sync": true,    // Enable bi-directional sync
  "prune_remote_files": false  // Keep remote files even if deleted locally
}
```

### Recommended Settings
- `two_way_sync: true` - Allows pull/sync commands to work properly
- `prune_remote_files: false` - Safer, prevents accidental remote file deletion

## Common Workflows

### Initial Setup
```bash
csync auth login
csync project create
csync push
```

### Daily Workflow
```bash
# Pull latest changes from Claude
csync pull

# Work on files locally...

# Push your changes
csync push

# Or do a full sync
csync sync
```

### Conflict Resolution
```bash
# Pull with merge to handle conflicts
csync pull --merge

# Or use sync with a strategy
csync sync --conflict-strategy=local-wins
```

## Command Aliases

All commands support both `claudesync` and `csync`:
```bash
claudesync push  # Old style
csync push       # New style (recommended)
```

## Migration Notes

- The old `push` command behavior has changed - it's now upload-only
- For the old bi-directional behavior, use `csync sync`
- All subprocess calls have been updated to use `csync`
