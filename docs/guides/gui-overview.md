# ClaudeSync GUI

A simple graphical interface for ClaudeSync using CustomTkinter.

## Installation

### Windows
1. **Easy way**: Double-click `ClaudeSync_GUI.bat`
2. **Direct**: Run `python -m scripts.launch_gui`

### Manual Installation
```bash
# Install GUI dependencies
pip install customtkinter pillow

# Run the GUI
python -m scripts.launch_gui
# OR if csync is in PATH:
csync-gui
```

## Features

### Implemented âœ…
- **Authentication Management**
  - Login/logout with session key
  - Real-time auth status
  - Easy Claude.ai access
  
- **Project Management**
  - List all projects
  - Create new projects
  - Set active project
  - View current project info
  
- **Sync Operations**
  - Push/Pull/Sync modes
  - File category selection
  - Dry run preview
  - Real-time output display
  - Progress indication
  
- **Workspace Management**
  - Discover local projects
  - Clone all remote projects
  - Batch operations support
  - Project quick access

- **UI Features**
  - Clean, modern interface
  - Dark/light mode (follows system)
  - Status indicators
  - Error handling with dialogs

### Coming Soon
- âš™ï¸ Settings configuration
- ðŸ“Š Sync history and logs
- ðŸ’¬ Chat management
- ðŸ”„ Auto-sync scheduling

## Architecture

The GUI is designed to be minimally invasive:
- Lives in `src/claudesync/gui/` (separate from CLI)
- Reuses existing sync logic via subprocess calls
- Optional dependency (won't affect CLI users)
- Separate entry point (`csync-gui`)

## Development

To add new features:
1. Create view in `src/claudesync/gui/views/`
2. Import and integrate in `main.py`
3. Call existing CLI commands via subprocess

## Notes

- The GUI calls `csync` CLI commands under the hood
- All existing CLI functionality remains unchanged
- GUI state is not persisted between sessions (uses live queries)

