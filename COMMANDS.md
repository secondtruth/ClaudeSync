# ClaudeSync Command Summary

## Available Commands

### Authentication & Setup
```bash
csync auth login
csync auth logout
csync auth status
```

### Project Management
```bash
csync project create
csync project set
csync project ls
csync project select [--multiple]
csync project instructions init  # Creates project-instructions.md
```

### Synchronization (Git-like)
```bash
csync push               # Upload only
csync pull               # Download only
csync sync               # Bi-directional sync
csync sync --dry-run     # Preview changes
```

### Workspace Management
```bash
csync workspace set-root /path/to/workspace
csync workspace discover
csync workspace sync-all
csync workspace status
```

### Remote Project Discovery
```bash
csync list-remote        # List all Claude projects
csync clone-all          # Clone all projects locally
csync clone-all --clean  # Remove empty dirs first
csync clone-all --skip-existing
```

### File Watching
```bash
csync watch start        # Watch for changes
csync watch start --daemon
csync watch stop
csync watch status
```

### Conflict Resolution
```bash
csync conflict detect
csync conflict resolve
csync conflict status
```

## Quick Start for Full Backup

1. **Set workspace root:**
   ```bash
   csync workspace set-root ~/claude-projects
   ```

2. **Clone all projects:**
   ```bash
   csync clone-all --clean
   ```

3. **Sync all projects:**
   ```bash
   csync workspace sync-all
   ```

4. **Initialize project instructions (per project):**
   ```bash
   cd ~/claude-projects/YourProject
   csync project instructions init
   ```

## Notes
- The `project-instructions.md` file is created with `csync project instructions init`
- Both `claudesync` and `csync` commands work identically
- Configuration: `~/.claudesync/config.json` (global), `.claudesync/config.local.json` (per project)
