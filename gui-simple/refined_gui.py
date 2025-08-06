#!/usr/bin/env python
"""
ClaudeSync Refined GUI - Modern, clean interface with Git-like commands
"""
import customtkinter as ctk
import sys
import subprocess
import threading
import queue
import json
import os
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, Dict, List, Tuple
import time

# Fix Windows Unicode issues
if sys.platform == "win32":
    import locale
    import codecs
    # Set UTF-8 as default encoding
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CSyncGUI:
    """Modern ClaudeSync GUI with improved architecture"""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync - Modern GUI")
        self.root.geometry("900x700")
        
        # State management
        self.state = {
            'authenticated': False,
            'organization': None,
            'project': None,
            'workspace': None,
            'syncing': False,
            'watching': False
        }
        
        # Process management
        self.current_process = None
        self.output_queue = queue.Queue()
        self.command_history = []
        
        # UI Components
        self.ui = {}
        
        # Create UI
        self.setup_ui()
        self.setup_keyboard_shortcuts()
        
        # Start background workers
        self.start_workers()
        
        # Initialize state
        self.check_initial_state()
    
    def setup_ui(self):
        """Create modern UI layout"""
        # Configure grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Header Frame
        self.create_header()
        
        # Main Content
        self.create_main_content()
        
        # Status Bar
        self.create_status_bar()
    
    def create_header(self):
        """Create header with status indicators"""
        header = ctk.CTkFrame(self.root, height=80)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)
        
        # Logo/Title
        title = ctk.CTkLabel(
            header, 
            text="ClaudeSync", 
            font=("Arial", 24, "bold")
        )
        title.grid(row=0, column=0, padx=20, pady=10)
        
        # Status Indicators
        status_frame = ctk.CTkFrame(header)
        status_frame.grid(row=0, column=1, sticky="e", padx=20)
        
        # Auth indicator
        self.ui['auth_indicator'] = ctk.CTkLabel(
            status_frame,
            text="● Not Connected",
            text_color="red",
            font=("Arial", 12)
        )
        self.ui['auth_indicator'].pack(anchor="e")
        
        # Project indicator
        self.ui['project_indicator'] = ctk.CTkLabel(
            status_frame,
            text="No Project",
            font=("Arial", 11)
        )
        self.ui['project_indicator'].pack(anchor="e")
        
        # Workspace indicator
        self.ui['workspace_indicator'] = ctk.CTkLabel(
            status_frame,
            text="",
            font=("Arial", 10),
            text_color="gray"
        )
        self.ui['workspace_indicator'].pack(anchor="e")
    
    def create_main_content(self):
        """Create main content area"""
        main = ctk.CTkFrame(self.root)
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.create_sidebar(main)
        
        # Terminal
        self.create_terminal(main)
    
    def create_sidebar(self, parent):
        """Create sidebar with organized commands"""
        sidebar = ctk.CTkScrollableFrame(parent, width=200)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        
        # Authentication Section
        self.create_section(sidebar, "Authentication", [
            ("Login", self.auth_login, "green"),
            ("Logout", self.auth_logout, "red")
        ])
        
        # Project Section
        self.create_section(sidebar, "Project", [
            ("Set Organization", self.set_organization),
            ("Create Project", self.create_project),
            ("Set Project", self.set_project),
            ("Switch Project", self.switch_project, "blue")
        ])
        
        # Sync Operations (Git-like)
        self.create_section(sidebar, "Sync Operations", [
            ("Push ↑", self.push, "green"),
            ("Pull ↓", self.pull, "blue"),
            ("Sync ↔", self.sync, "orange"),
            ("Status", self.show_status)
        ])
        
        # Workspace
        self.create_section(sidebar, "Workspace", [
            ("Set Root", self.set_workspace_root),
            ("Discover", self.discover_projects),
            ("Sync All", self.sync_all_projects, "green"),
            ("Clone All", self.clone_all_projects, "blue")
        ])
        
        # Advanced
        self.create_section(sidebar, "Advanced", [
            ("List Files", self.list_files),
            ("Pull Chats", self.pull_chats),
            ("Watch Toggle", self.toggle_watch),
            ("Settings", self.show_settings, "gray")
        ])
    
    def create_section(self, parent, title: str, buttons: List[Tuple]):
        """Create a section with title and buttons"""
        # Section title
        label = ctk.CTkLabel(
            parent,
            text=title,
            font=("Arial", 12, "bold")
        )
        label.pack(pady=(15, 5), anchor="w", padx=10)
        
        # Section buttons
        for button_info in buttons:
            name = button_info[0]
            command = button_info[1]
            color = button_info[2] if len(button_info) > 2 else None
            
            btn = ctk.CTkButton(
                parent,
                text=name,
                command=command,
                width=180,
                height=32,
                fg_color=color if color else None
            )
            btn.pack(pady=2, padx=10, fill="x")
    
    def create_terminal(self, parent):
        """Create terminal output area"""
        terminal_frame = ctk.CTkFrame(parent)
        terminal_frame.grid(row=0, column=1, sticky="nsew")
        terminal_frame.grid_rowconfigure(0, weight=1)
        terminal_frame.grid_columnconfigure(0, weight=1)
        
        # Terminal header
        header = ctk.CTkFrame(terminal_frame, height=40)
        header.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkLabel(
            header,
            text="Terminal Output",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=10, pady=5)
        
        ctk.CTkButton(
            header,
            text="Clear",
            command=self.clear_terminal,
            width=60,
            height=28
        ).pack(side="right", padx=10, pady=5)
        
        # Terminal text widget
        self.ui['terminal'] = ctk.CTkTextbox(
            terminal_frame,
            font=("Consolas", 11),
            wrap="word"
        )
        self.ui['terminal'].grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    def create_status_bar(self):
        """Create status bar at bottom"""
        status_bar = ctk.CTkFrame(self.root, height=30)
        status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        status_bar.grid_columnconfigure(0, weight=1)
        
        # Status text
        self.ui['status_text'] = ctk.CTkLabel(
            status_bar,
            text="Ready",
            font=("Arial", 10)
        )
        self.ui['status_text'].pack(side="left", padx=10)
        
        # Progress indicator (hidden by default)
        self.ui['progress'] = ctk.CTkProgressBar(status_bar, width=200)
        
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind("<Control-p>", lambda e: self.push())
        self.root.bind("<Control-l>", lambda e: self.pull())
        self.root.bind("<Control-s>", lambda e: self.sync())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-k>", lambda e: self.clear_terminal())
    
    def start_workers(self):
        """Start background workers"""
        # Queue processor
        self.process_queue()
        # Status updater
        self.update_status_loop()
    
    def check_initial_state(self):
        """Check authentication and project status"""
        self.check_auth()
        self.check_project_status()
        self.check_workspace()
    
    # Core functionality methods
    def run_command(self, args: List[str], capture_output=False, show_output=True):
        """Run csync command"""
        try:
            cmd = ["csync"] + args
            self.log(f"$ csync {' '.join(args)}", color="blue")
            
            # Set encoding for Windows
            env = os.environ.copy()
            if sys.platform == "win32":
                env['PYTHONIOENCODING'] = 'utf-8'
            
            if capture_output:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env
                )
                if show_output and result.stdout:
                    self.log(result.stdout)
                if result.stderr:
                    self.log(result.stderr, color="red")
                return result
            else:
                # Stream output
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    env=env
                )
                
                # Start output reader thread
                threading.Thread(
                    target=self.read_process_output,
                    daemon=True
                ).start()
                
        except Exception as e:
            self.log(f"Error: {str(e)}", color="red")
    
    def read_process_output(self):
        """Read process output in background"""
        if not self.current_process:
            return
        
        for line in iter(self.current_process.stdout.readline, ''):
            if line:
                self.output_queue.put(('stdout', line.rstrip()))
        
        for line in iter(self.current_process.stderr.readline, ''):
            if line:
                self.output_queue.put(('stderr', line.rstrip()))
    
    def log(self, message: str, color: str = None):
        """Log message to terminal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message
        if color == "red":
            formatted = f"[{timestamp}] ❌ {message}"
        elif color == "green":
            formatted = f"[{timestamp}] ✅ {message}"
        elif color == "blue":
            formatted = f"[{timestamp}] ➤ {message}"
        else:
            formatted = f"[{timestamp}] {message}"
        
        # Add to terminal
        self.ui['terminal'].insert("end", formatted + "\n")
        self.ui['terminal'].see("end")
    
    def clear_terminal(self):
        """Clear terminal output"""
        self.ui['terminal'].delete("0.0", "end")
        self.log("Terminal cleared", color="blue")
    
    def process_queue(self):
        """Process output queue"""
        try:
            while True:
                stream, line = self.output_queue.get_nowait()
                if stream == 'stderr':
                    self.log(line, color="red")
                else:
                    self.log(line)
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_queue)
    
    def update_status_loop(self):
        """Update status indicators periodically"""
        # Check auth status every 30 seconds
        if hasattr(self, '_status_counter'):
            self._status_counter += 1
        else:
            self._status_counter = 0
        
        if self._status_counter % 300 == 0:  # Every 30 seconds
            self.check_auth()
            self.check_project_status()
        
        self.root.after(100, self.update_status_loop)
    
    # Authentication methods
    def check_auth(self):
        """Check authentication status"""
        # Try to get organization list as a proxy for auth status
        result = self.run_command(["organization", "ls"], capture_output=True, show_output=False)
        
        # If we can list organizations, we're authenticated
        if result and result.returncode == 0:
            self.state['authenticated'] = True
            self.ui['auth_indicator'].configure(text="● Connected", text_color="green")
        else:
            # Fallback to auth ls check
            result = self.run_command(["auth", "ls"], capture_output=True, show_output=False)
            if result and result.returncode == 0 and result.stdout:
                # Check for various success indicators
                auth_success = any([
                    "claude.ai" in result.stdout.lower(),
                    "active" in result.stdout.lower(),
                    "logged in" in result.stdout.lower(),
                    "authenticated" in result.stdout.lower()
                ])
                if auth_success:
                    self.state['authenticated'] = True
                    self.ui['auth_indicator'].configure(text="● Connected", text_color="green")
                else:
                    self.state['authenticated'] = False
                    self.ui['auth_indicator'].configure(text="● Not Connected", text_color="red")
            else:
                self.state['authenticated'] = False
                self.ui['auth_indicator'].configure(text="● Not Connected", text_color="red")
    
    def auth_login(self):
        """Login to Claude.ai"""
        self.log("Starting authentication...", color="blue")
        # Open in new terminal for interactive login
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "auth", "login"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "auth", "login"])
        self.log("Complete login in the terminal window, then check status", color="green")
        # Schedule auth check
        self.root.after(5000, self.check_auth)
    
    def auth_logout(self):
        """Logout from Claude.ai"""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to logout?"):
            self.run_command(["auth", "logout"])
            self.check_auth()
    
    # Project methods
    def check_project_status(self):
        """Check current project"""
        try:
            config_file = Path(".claudesync/config.local.json")
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    project_name = config.get("active_project_name", "Unknown")
                    self.state['project'] = project_name
                    self.ui['project_indicator'].configure(text=f"📁 {project_name}")
            else:
                self.state['project'] = None
                self.ui['project_indicator'].configure(text="No Project")
        except Exception as e:
            self.state['project'] = None
            self.ui['project_indicator'].configure(text="No Project")
    
    def set_organization(self):
        """Set organization"""
        if not self.state['authenticated']:
            self.log("Please login first", color="red")
            return
        
        self.log("Setting organization...", color="blue")
        self.run_command(["organization", "set"])
    
    def create_project(self):
        """Create new project"""
        if not self.state['authenticated']:
            self.log("Please login first", color="red")
            return
        
        name = tk.simpledialog.askstring("Create Project", "Enter project name:")
        if name:
            self.log(f"Creating project: {name}", color="blue")
            self.run_command(["project", "create", "--name", name])
            self.check_project_status()
    
    def set_project(self):
        """Set active project"""
        if not self.state['authenticated']:
            self.log("Please login first", color="red")
            return
        
        self.log("Setting project...", color="blue")
        self.run_command(["project", "set"])
        self.root.after(2000, self.check_project_status)
    
    def switch_project(self):
        """Quick project switcher"""
        self.log("Discovering projects...", color="blue")
        result = self.run_command(["workspace", "discover"], capture_output=True)
        if result and result.returncode == 0:
            self.log("Check terminal for available projects")
    
    # Git-like sync operations
    def push(self):
        """Push local changes to remote"""
        if not self.state['project']:
            self.log("No project set", color="red")
            return
        
        self.log("Pushing changes to Claude.ai...", color="green")
        self.ui['status_text'].configure(text="Pushing...")
        self.state['syncing'] = True
        self.run_command(["push"])
        self.state['syncing'] = False
        self.ui['status_text'].configure(text="Ready")
    
    def pull(self):
        """Pull remote changes"""
        if not self.state['project']:
            self.log("No project set", color="red")
            return
        
        self.log("Pulling changes from Claude.ai...", color="blue")
        self.ui['status_text'].configure(text="Pulling...")
        self.state['syncing'] = True
        self.run_command(["pull"])
        self.state['syncing'] = False
        self.ui['status_text'].configure(text="Ready")
    
    def sync(self):
        """Bidirectional sync"""
        if not self.state['project']:
            self.log("No project set", color="red")
            return
        
        self.log("Performing bidirectional sync...", color="orange")
        self.ui['status_text'].configure(text="Syncing...")
        self.state['syncing'] = True
        self.run_command(["sync"])
        self.state['syncing'] = False
        self.ui['status_text'].configure(text="Ready")
    
    def show_status(self):
        """Show sync status"""
        self.log("Checking status...", color="blue")
        self.run_command(["status"])
    
    # Workspace methods
    def check_workspace(self):
        """Check workspace configuration"""
        result = self.run_command(["workspace", "status"], capture_output=True, show_output=False)
        if result and "Workspace root:" in result.stdout:
            for line in result.stdout.split('\n'):
                if "Workspace root:" in line:
                    workspace = line.split("Workspace root:")[-1].strip()
                    if workspace and workspace != "Not set":
                        # Shorten path for display
                        display_path = workspace
                        if len(display_path) > 40:
                            display_path = "..." + display_path[-37:]
                        self.ui['workspace_indicator'].configure(text=f"📂 {display_path}")
                        self.state['workspace'] = workspace
                        return
        
        self.ui['workspace_indicator'].configure(text="")
        self.state['workspace'] = None
    
    def set_workspace_root(self):
        """Set workspace root directory"""
        directory = filedialog.askdirectory(title="Select Workspace Root")
        if directory:
            self.log(f"Setting workspace root to: {directory}", color="blue")
            self.run_command(["workspace", "set-root", directory])
            self.check_workspace()
    
    def discover_projects(self):
        """Discover projects in workspace"""
        if not self.state['workspace']:
            self.log("Please set workspace root first", color="red")
            return
        
        self.log("Discovering projects...", color="blue")
        self.run_command(["workspace", "discover"])
    
    def sync_all_projects(self):
        """Sync all projects in workspace"""
        if not self.state['workspace']:
            self.log("Please set workspace root first", color="red")
            return
        
        self.log("Syncing all projects in workspace...", color="green")
        self.ui['status_text'].configure(text="Syncing all...")
        self.run_command(["workspace", "sync-all"])
        self.ui['status_text'].configure(text="Ready")
    
    def clone_all_projects(self):
        """Clone all remote projects"""
        if not self.state['authenticated']:
            self.log("Please login first", color="red")
            return
        
        self.log("Cloning all remote projects...", color="blue")
        # Open in terminal for interactive selection
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "workspace", "clone"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "workspace", "clone"])
        self.log("Check terminal for clone progress")
    
    # Advanced operations
    def list_files(self):
        """List project files"""
        if not self.state['project']:
            self.log("No project set", color="red")
            return
        
        self.log("Listing project files...", color="blue")
        self.run_command(["project", "file", "ls"])
    
    def pull_chats(self):
        """Pull chat history"""
        if not self.state['project']:
            self.log("No project set", color="red")
            return
        
        self.log("Pulling chat history...", color="blue")
        self.run_command(["chat", "pull"])
    
    def toggle_watch(self):
        """Toggle file watching"""
        if self.state['watching']:
            self.log("Stopping file watcher...", color="red")
            self.run_command(["watch", "stop"])
            self.state['watching'] = False
        else:
            self.log("Starting file watcher...", color="green")
            self.run_command(["watch", "start"])
            self.state['watching'] = True
    
    def show_settings(self):
        """Show settings dialog"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x400")
        settings_window.transient(self.root)
        
        # Title
        ctk.CTkLabel(
            settings_window,
            text="ClaudeSync Settings",
            font=("Arial", 16, "bold")
        ).pack(pady=20)
        
        # Settings frame
        frame = ctk.CTkFrame(settings_window)
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Common settings
        settings = [
            ("Max File Size (bytes):", "max_file_size", "32768"),
            ("Upload Delay (seconds):", "upload_delay", "0.5"),
            ("Log Level:", "log_level", ["INFO", "DEBUG", "WARNING", "ERROR"])
        ]
        
        for i, (label, key, default) in enumerate(settings):
            ctk.CTkLabel(frame, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="w")
            
            if isinstance(default, list):
                # Dropdown
                var = ctk.StringVar(value=default[0])
                dropdown = ctk.CTkComboBox(frame, values=default, variable=var)
                dropdown.grid(row=i, column=1, padx=10, pady=5)
                dropdown._key = key
            else:
                # Entry
                entry = ctk.CTkEntry(frame, placeholder_text=default)
                entry.grid(row=i, column=1, padx=10, pady=5)
                entry._key = key
        
        # Apply button
        def apply_settings():
            for widget in frame.winfo_children():
                if hasattr(widget, '_key'):
                    key = widget._key
                    value = widget.get()
                    self.run_command(["config", "set", key, value])
            self.log("Settings updated", color="green")
            settings_window.destroy()
        
        ctk.CTkButton(
            settings_window,
            text="Apply",
            command=apply_settings
        ).pack(pady=20)
    
    def run(self):
        """Start the GUI"""
        self.log("ClaudeSync GUI started", color="green")
        self.log("Use 'csync' commands or buttons above", color="blue")
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = CSyncGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nGUI closed")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
