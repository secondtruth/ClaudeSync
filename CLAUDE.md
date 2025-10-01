# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClaudeSync is a Python CLI tool for synchronizing local files and directories with Claude.ai projects. It supports both single-project sync (legacy `claudesync`) and workspace-wide sync (`csync`) for managing multiple projects simultaneously.

**Two CLI Interfaces:**
- **Legacy CLI** (`claudesync`): Traditional per-project sync with granular control
- **Minimal CLI** (`csync`): Workspace-wide sync for all Claude.ai projects at once

## Recent Implementation: Minimal CLI (Current)

The `csync` minimal CLI was recently refactored to provide a simple, workspace-focused interface:

**Commands:**
- `csync auth login/logout/status` - Session key authentication
- `csync workspace init <path>` - Initialize workspace directory
- `csync workspace sync` - Sync all projects with flags:
  - `--bidirectional` - Upload local changes to Claude.ai
  - `--chats` - Include chat conversations
  - `--conflict <strategy>` - Conflict resolution (remote/local/newer)
  - `--dry-run` - Preview without syncing
- `csync workspace status` - Show workspace status and tracked projects
- `csync workspace diff` - Audit local vs remote differences (added in commit 4a8b409)
  - `--detailed` - Show file-level diffs
  - `--json` - JSON output
- `csync gui` - Launch system tray application

**Key Features:**
- Centralized workspace config at `~/.claudesync/workspace.json`
- Preserves emoji characters in project folder names
- Safe Unicode printing with `safe_print()` helper
- Legacy `push`/`pull` commands redirect to `workspace sync` (hidden)

## Development Commands

### Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .
```

### Testing
```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_happy_path
```

### Code Style
- Follow the **black** style guide for Python code
- Run black formatter before committing

## Architecture

### Core Components

**Configuration Management** (`configmanager/`)
- `FileConfigManager`: Manages global config (`~/.claudesync/config.json`) and local project config (`.claudesync/config.local.json`)
- Supports hierarchical config with global defaults and project-specific overrides
- Session key storage is handled separately per provider via `SessionKeyManager`

**Provider System** (`providers/`)
- `BaseProvider`: Abstract interface for API providers
- `BaseClaudeAIProvider`: Base implementation for Claude.ai API
- `ClaudeAIProvider`: Concrete implementation using urllib for HTTP requests
- Factory pattern via `provider_factory.py` for extensibility

**Sync Engines**
- `SyncManager` (`syncmanager.py`): Per-project sync with compression support, two-way sync, and conflict resolution
- `WorkspaceSync` (`workspace_sync.py`): Workspace-wide multi-project sync engine (used by minimal CLI)
  - **Main method**: `sync_all(dry_run, bidirectional, sync_chats, conflict_strategy)` - syncs all projects
  - **Analysis**: `analyze_diff(provider, detailed)` - audits local vs remote differences
  - **Status**: `status()` - returns workspace status without authentication
  - Discovers all Claude.ai projects and syncs to individual folders
  - Supports bidirectional sync, chat conversations, and conflict strategies
  - Preserves emojis in folder names via `_sanitize_name()` method
  - Centralized config at `~/.claudesync/workspace.json` with project_map

**CLI Structure** (`cli/`)
- `main.py`: Legacy claudesync CLI entry point with full command suite
- `minimal_cli.py`: Simplified csync CLI for workspace operations
  - Authentication: `csync auth login/logout/status`
  - Workspace: `csync workspace init/sync/status/diff`
  - GUI: `csync gui`

### Key Patterns

**Authentication Flow**
1. User provides session key (starts with `sk-ant`)
2. Provider stores key via `config.set_session_key(provider, key, expiry)`
3. All API requests include session key in cookies

**Sync Flow (WorkspaceSync)**
1. Fetch all projects from organization
2. For each project:
   - Determine local folder (sanitized name with emojis preserved)
   - Download remote files and compare with local
   - Handle bidirectional sync if enabled
   - Apply conflict resolution strategy (remote/local/newer)
3. Optionally sync chat conversations to `claude_chats/` subfolder

**Conflict Resolution Strategies**
- `remote`: Always use remote version (default)
- `local`: Always use local version
- `newer`: Use file with most recent modification time
- `prompt`: Ask user for each conflict (interactive)

### Important Files

**Entry Points**
- `cli/main.py`: Legacy claudesync command tree
- `cli/minimal_cli.py`: Simplified csync workspace commands
- `gui/gui_main.py`: Tkinter-based GUI with system tray

**Core Sync Logic**
- `workspace_sync.py`: Multi-project workspace sync
- `syncmanager.py`: Single project sync with compression
- `chat_sync.py`: Chat conversation synchronization

**Utilities**
- `utils.py`: File hashing (MD5), file discovery, provider validation
- `compression.py`: gzip compression for efficient uploads
- `conflict_resolver.py`: Conflict detection and resolution strategies

### Background Services

**Sync Agent** (`agent/sync_agent.py`)
- Provides continuous bidirectional sync (Drive-style)
- Uses watchdog for filesystem monitoring
- Polls remote for changes at configurable intervals
- Supports multiple projects simultaneously

**GUI** (`gui/`)
- `gui_main.py`: Main tkinter application
- `systray.py`: System tray integration for background sync

## Configuration Files

**Global Config** (`~/.claudesync/config.json`)
- Active organization/project IDs
- Upload delay, compression settings
- Default category, two-way sync settings

**Local Config** (`.claudesync/config.local.json` in project root)
- Project-specific overrides
- Submodule configurations

**Workspace Config** (`~/.claudesync/workspace.json`)
- Workspace root path
- Project ID to folder name mapping
- Last sync timestamp

## Emoji Support

The codebase explicitly supports emoji characters in project names and preserves them in folder structures. Use `safe_print()` from `workspace_sync.py` for console output to handle Unicode encoding issues gracefully.

## Submodules

ClaudeSync supports nested projects (submodules) where a parent project can contain child projects. Each submodule syncs to its own Claude.ai project while residing in a subdirectory of the parent.

## Testing Notes

- Mock HTTP server available in `tests/mock_http_server.py`
- Use `InMemoryConfigManager` for testing instead of `FileConfigManager`
- Test files use custom `LoggingTestCase` base class for verbose output

## Common Development Tasks

**Adding a new minimal CLI command:**
1. Add command function to `cli/minimal_cli.py` under appropriate group (`@auth.command()`, `@workspace.command()`, etc.)
2. Use Click decorators: `@click.option()`, `@click.argument()`
3. Use `get_provider_with_auth()` helper for authenticated commands
4. Use `safe_print()` for output with emoji/Unicode characters
5. Handle errors gracefully with try/except and descriptive messages

**Adding workspace analysis features:**
1. Add method to `WorkspaceSync` class in `workspace_sync.py`
2. Example: `analyze_diff()` method added for workspace diff command
3. Return structured data (dict) for easy JSON serialization
4. Use `safe_print()` when displaying Unicode project names

**Adding a new sync strategy:**
1. Extend conflict resolution in `conflict_resolver.py`
2. Update `ConflictResolution` enum if adding new strategy
3. Add handling in `WorkspaceSync._sync_project()` or `SyncManager.sync()`

**Working with the provider API:**
- All API calls go through provider methods (get_projects, list_files, etc.)
- Use retry decorator `@retry_on_403` for resilient API calls
- Check `base_claude_ai.py` for available API methods

**Workspace Config Structure:**
```json
{
  "workspace_root": "/path/to/workspace",
  "project_map": {
    "project-uuid": "📁 Project Name",
    ...
  },
  "last_sync": "2025-10-01T16:13:00"
}
```
