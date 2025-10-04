# ClaudeSync Simple GUI

A streamlined terminal-style GUI for ClaudeSync with essential buttons for common operations.

## Features

- **Terminal Output**: Real-time command output display
- **One-Click Operations**: Simple buttons for all core functions
- **Clean Interface**: Minimal, focused design
- **Status Indicators**: Clear authentication and project status
- **Workspace Management**: Multi-project support with quick switching
- **Settings Dialog**: Interactive configuration management
- **File Watching**: Toggle automatic sync on file changes

## Core Functions

### Authentication
- Login/Logout with status indicator
- Opens separate terminal for interactive auth

### Project Management  
- Set Organization
- Create Project (current directory)
- Set Project (existing)
- Real-time project status display

### File Operations
- **Push**: Upload files to Claude
- **Pull**: Download files from Claude  
- **Sync**: Bidirectional sync
- **List Files**: Show remote files

### Workspace Management
- **Workspace**: Show workspace operations menu
- **Sync All**: Sync all projects in workspace
- **Clone All**: Clone all remote projects
- **Switch Project**: Quick project switcher with dialog

### Additional Features
- **Chat Pull**: Download conversation history
- **Settings**: Interactive settings dialog
- **Clear Terminal**: Clean output display
- **Watch**: Toggle file watching for auto-sync

## Usage

1. **Launch (repo checkout)**: python -m scripts.launch_gui --variant simple
   - Prep dependencies first with python -m scripts.launch_gui --variant simple --deps-only
2. **Launch (installed package)**: python gui-simple/simple_gui.py
3. **Login**: Click Login button and follow terminal prompts
4. **Set Organization**: Required after first login
5. **Create/Set Project**: Initialize or connect to project
6. **Use Sync Operations**: Push/Pull/Sync as needed

### Keyboard Shortcuts

- Ctrl+P - Push files
- Ctrl+L - Pull files  
- Ctrl+S - Sync files
- Ctrl+W - Workspace menu
- Ctrl+K - Clear terminal
- F5 - Refresh status
- Ctrl+Q - Quit

## Requirements

- Python 3.8+
- customtkinter
- ClaudeSync installed (pip install claudesync)

## Installation

`ash
# Install ClaudeSync if not already installed
pip install claudesync

# Install GUI dependency
pip install customtkinter

# Run the simple GUI directly
python gui-simple/simple_gui.py
`

## Design Philosophy

This simple GUI focuses on:
- Essential operations only
- Terminal-style output for transparency
- Minimal dependencies
- Fast and responsive interface
- Clear status feedback

## Differences from Full GUI

| Feature | Full GUI | Simple GUI |
|---------|----------|------------|
| Interface | Multi-tab | Single window |
| Terminal | Hidden/Toggle | Always visible |
| Workspace Mgmt | Complex UI | Simple buttons + dialogs |
| Settings | Dedicated tab | Interactive dialog |
| Project Switch | Multiple views | Quick selector dialog |
| File Watch | Buried in menus | One-click toggle |
| Conflict Resolution | GUI dialogs | Terminal only |
| Progress Bars | Visual | Terminal text |

## Troubleshooting

- **"csync not found"**: Install ClaudeSync with pip install claudesync
- **GUI won't start**: Install customtkinter with pip install customtkinter
- **Auth fails**: Check terminal window for detailed error messages
