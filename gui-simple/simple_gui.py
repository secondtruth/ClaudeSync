#!/usr/bin/env python
"""
ClaudeSync Simple GUI - Terminal-style interface with buttons
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
from tkinter import filedialog, simpledialog

# Set appearance
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class SimpleSyncGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync - Simple GUI")
        self.root.geometry("800x600")
        
        # State
        self.authenticated = False
        self.current_org = None
        self.current_project = None
        self.process = None
        
        # Terminal output queue
        self.output_queue = queue.Queue()
        
        # Create UI
        self.setup_ui()
        
        # Bind keyboard shortcuts
        self.setup_shortcuts()
        
        # Start queue processor
        self.process_queue()
        
        # Check initial auth status
        self.check_auth()
    
    def setup_ui(self):
        """Create the simple UI layout"""
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Button frame (top)
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        # Row 1: Authentication
        auth_row = ctk.CTkFrame(button_frame)
        auth_row.pack(fill="x", pady=2)
        
        self.auth_button = ctk.CTkButton(
            auth_row, text="Login", 
            command=self.auth_login, width=120
        )
        self.auth_button.pack(side="left", padx=2)
        
        ctk.CTkButton(
            auth_row, text="Logout", 
            command=self.auth_logout, width=120
        ).pack(side="left", padx=2)
        
        self.auth_status = ctk.CTkLabel(auth_row, text="Not authenticated")
        self.auth_status.pack(side="left", padx=10)
        
        # Row 2: Organization/Project
        org_row = ctk.CTkFrame(button_frame)
        org_row.pack(fill="x", pady=2)
        
        ctk.CTkButton(
            org_row, text="Set Organization", 
            command=self.set_organization, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            org_row, text="Create Project", 
            command=self.create_project, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            org_row, text="Set Project", 
            command=self.set_project, width=120
        ).pack(side="left", padx=2)
        
        self.project_status = ctk.CTkLabel(org_row, text="No project")
        self.project_status.pack(side="left", padx=10)
        
        # Workspace status (right side)
        self.workspace_status = ctk.CTkLabel(org_row, text="", fg_color="gray20", corner_radius=5)
        self.workspace_status.pack(side="right", padx=10)
        
        # Row 3: Sync operations
        sync_row = ctk.CTkFrame(button_frame)
        sync_row.pack(fill="x", pady=2)
        
        ctk.CTkButton(
            sync_row, text="Push", 
            command=self.push_files, width=120,
            fg_color="green"
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            sync_row, text="Pull", 
            command=self.pull_files, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            sync_row, text="Sync", 
            command=self.sync_files, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            sync_row, text="List Files", 
            command=self.list_files, width=120
        ).pack(side="left", padx=2)
        
        # Row 4: Workspace operations
        workspace_row = ctk.CTkFrame(button_frame)
        workspace_row.pack(fill="x", pady=2)
        
        ctk.CTkButton(
            workspace_row, text="Workspace", 
            command=self.workspace_menu, width=120,
            fg_color="purple"
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            workspace_row, text="Sync All", 
            command=self.sync_all_projects, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            workspace_row, text="Clone All", 
            command=self.clone_all_projects, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            workspace_row, text="Switch Project", 
            command=self.switch_project, width=120
        ).pack(side="left", padx=2)
        
        # Row 5: Additional operations & Settings
        extra_row = ctk.CTkFrame(button_frame)
        extra_row.pack(fill="x", pady=2)
        
        ctk.CTkButton(
            extra_row, text="Chat Pull", 
            command=self.pull_chats, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            extra_row, text="Settings", 
            command=self.settings_menu, width=120,
            fg_color="gray"
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            extra_row, text="Clear Terminal", 
            command=self.clear_terminal, width=120
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            extra_row, text="Watch", 
            command=self.toggle_watch, width=120
        ).pack(side="left", padx=2)
        
        # Terminal output (bottom)
        terminal_frame = ctk.CTkFrame(main_frame)
        terminal_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Terminal header
        terminal_header = ctk.CTkFrame(terminal_frame)
        terminal_header.pack(fill="x")
        
        ctk.CTkLabel(
            terminal_header, text="Terminal Output", 
            font=("Consolas", 14, "bold")
        ).pack(side="left", padx=5)
        
        # Terminal text area
        self.terminal = ctk.CTkTextbox(
            terminal_frame, 
            font=("Consolas", 11),
            fg_color="#1e1e1e",
            text_color="#cccccc"
        )
        self.terminal.pack(fill="both", expand=True, padx=2, pady=2)
    
    def run_command(self, args, capture_output=True):
        """Run a csync command and capture output"""
        cmd = ["csync"] + args
        
        self.log(f"$ {' '.join(cmd)}")
        
        if capture_output:
            # Run with output capture
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd()
                )
                
                if result.stdout:
                    self.log(result.stdout)
                if result.stderr:
                    self.log(result.stderr, error=True)
                
                return result
            except Exception as e:
                self.log(f"Error: {str(e)}", error=True)
                return None
        else:
            # Run interactively (for auth)
            try:
                subprocess.run(cmd, cwd=os.getcwd())
            except Exception as e:
                self.log(f"Error: {str(e)}", error=True)
    
    def log(self, message, error=False):
        """Thread-safe logging to terminal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_queue.put((f"[{timestamp}] {message}\n", error))
    
    def process_queue(self):
        """Process output queue"""
        try:
            while True:
                message, is_error = self.output_queue.get_nowait()
                self.terminal.insert("end", message)
                if is_error:
                    # Would style error text red if customtkinter supported it
                    pass
                self.terminal.see("end")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_queue)
    
    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal.delete("1.0", "end")
        self.log("Terminal cleared")
    
    def check_auth(self):
        """Check authentication status"""
        result = self.run_command(["auth", "ls"])
        if result and result.returncode == 0:
            self.authenticated = True
            self.auth_status.configure(text="✓ Authenticated")
            self.auth_button.configure(text="Re-login")
            
            # Check for current project
            self.check_project_status()
        else:
            self.authenticated = False
            self.auth_status.configure(text="Not authenticated")
    
    def check_project_status(self):
        """Check current project configuration"""
        try:
            # Check for .claudesync directory
            if os.path.exists(".claudesync/config.local.json"):
                with open(".claudesync/config.local.json", "r") as f:
                    config = json.load(f)
                    project_name = config.get("active_project_name", "Unknown")
                    self.project_status.configure(text=f"Project: {project_name}")
                    self.current_project = project_name
            else:
                self.project_status.configure(text="No project set")
                self.current_project = None
        except Exception as e:
            self.log(f"Error reading project config: {str(e)}", error=True)
        
        # Check workspace status
        self.check_workspace_status()
    
    def check_workspace_status(self):
        """Check workspace configuration"""
        try:
            ws_config_path = os.path.expanduser("~/.claudesync/workspace.json")
            if os.path.exists(ws_config_path):
                with open(ws_config_path, "r") as f:
                    ws_config = json.load(f)
                    ws_root = ws_config.get("workspace_root")
                    if ws_root:
                        # Shorten path for display
                        display_path = ws_root
                        if len(display_path) > 30:
                            display_path = "..." + display_path[-27:]
                        self.workspace_status.configure(text=f"WS: {display_path}")
                    else:
                        self.workspace_status.configure(text="WS: Auto-discover")
            else:
                self.workspace_status.configure(text="")
        except:
            pass
    
    def auth_login(self):
        """Handle authentication"""
        self.log("Starting authentication...")
        self.log("Please check the terminal window that opens for the login process.")
        
        # Run auth login in separate terminal
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "auth", "login"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "auth", "login"])
        
        self.log("After completing login in the terminal, click any button to refresh status.")
    
    def auth_logout(self):
        """Handle logout"""
        result = self.run_command(["auth", "logout"])
        if result and result.returncode == 0:
            self.authenticated = False
            self.auth_status.configure(text="Not authenticated")
            self.auth_button.configure(text="Login")
            self.log("Logged out successfully")
    
    def set_organization(self):
        """Set organization"""
        if not self.authenticated:
            self.log("Please login first", error=True)
            return
        
        self.run_command(["organization", "ls"])
        self.log("\nStarting organization selection...")
        
        # Run interactively in new terminal
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "organization", "set"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "organization", "set"])
    
    def create_project(self):
        """Create new project"""
        if not self.authenticated:
            self.log("Please login first", error=True)
            return
        
        self.log("Creating new project in current directory...")
        result = self.run_command(["project", "create"])
        if result and result.returncode == 0:
            self.check_project_status()
    
    def set_project(self):
        """Set existing project"""
        if not self.authenticated:
            self.log("Please login first", error=True)
            return
        
        self.log("Listing available projects...")
        self.run_command(["project", "ls"])
        
        # Run interactively in new terminal
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "project", "set"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "project", "set"])
    
    def push_files(self):
        """Push files to Claude"""
        if not self.current_project:
            self.log("No project set", error=True)
            return
        
        self.log("Pushing files to Claude...")
        self.run_command(["push"])
    
    def pull_files(self):
        """Pull files from Claude"""
        if not self.current_project:
            self.log("No project set", error=True)
            return
        
        self.log("Pulling files from Claude...")
        self.run_command(["pull"])
    
    def sync_files(self):
        """Sync files with Claude"""
        if not self.current_project:
            self.log("No project set", error=True)
            return
        
        self.log("Syncing files with Claude...")
        self.run_command(["sync"])
    
    def list_files(self):
        """List project files"""
        if not self.current_project:
            self.log("No project set", error=True)
            return
        
        self.log("Listing project files...")
        self.run_command(["project", "file", "ls"])
    
    def pull_chats(self):
        """Pull chat history"""
        if not self.current_project:
            self.log("No project set", error=True)
            return
        
        self.log("Pulling chat history...")
        self.run_command(["chat", "pull"])
    
    def show_settings(self):
        """Show configuration settings"""
        self.log("Current configuration:")
        self.run_command(["config", "ls"])
    
    def workspace_menu(self):
        """Show workspace operations menu"""
        self.log("\n=== WORKSPACE OPERATIONS ===")
        self.log("1. Set workspace root directory")
        self.log("2. Discover projects in workspace")
        self.log("3. Show workspace status")
        self.log("4. Reset workspace configuration")
        self.log("\nUse the buttons above or run these commands:")
        self.log("  csync workspace set-root <path>")
        self.log("  csync workspace discover")
        self.log("  csync workspace status")
        self.log("  csync workspace reset")
        
        # Show current workspace status
        self.run_command(["workspace", "status"])
    
    def sync_all_projects(self):
        """Sync all projects in workspace"""
        self.log("Syncing all projects in workspace...")
        self.run_command(["workspace", "sync-all"])
    
    def clone_all_projects(self):
        """Clone all remote projects"""
        self.log("Cloning all remote projects...")
        # Run in new terminal for interactive selection
        if sys.platform == "win32":
            subprocess.Popen(["start", "cmd", "/k", "csync", "workspace", "clone"], shell=True)
        else:
            subprocess.Popen(["gnome-terminal", "--", "csync", "workspace", "clone"])
        self.log("Check the terminal window for clone progress...")
    
    def switch_project(self):
        """Quick switch between projects with dialog"""
        self.log("Discovering projects...")
        result = self.run_command(["workspace", "discover", "--json"], capture_output=True)
        
        if result and result.returncode == 0:
            try:
                # Parse JSON output if available
                projects = json.loads(result.stdout)
                if projects:
                    # Create project selector window
                    self.show_project_selector(projects)
                else:
                    self.log("No projects found in workspace")
            except:
                # Fallback to text instructions
                self.log("\nTo switch project, navigate to the project directory and click 'Set Project'")
                self.log("Or run: cd <project-path> && csync project set")
    
    def show_project_selector(self, projects):
        """Show project selection dialog"""
        selector = ctk.CTkToplevel(self.root)
        selector.title("Select Project")
        selector.geometry("500x400")
        selector.transient(self.root)
        
        # Title
        ctk.CTkLabel(
            selector,
            text="Select a Project",
            font=("Arial", 16, "bold")
        ).pack(pady=10)
        
        # Project list frame
        list_frame = ctk.CTkFrame(selector)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Scrollable frame for projects
        for project in projects:
            proj_frame = ctk.CTkFrame(list_frame)
            proj_frame.pack(fill="x", pady=2, padx=5)
            
            # Project info
            name_label = ctk.CTkLabel(
                proj_frame,
                text=f"{project.get('name', 'Unknown')}",
                font=("Arial", 12, "bold")
            )
            name_label.pack(side="left", padx=10)
            
            path_label = ctk.CTkLabel(
                proj_frame,
                text=f"{project.get('path', '')}",
                font=("Arial", 10)
            )
            path_label.pack(side="left", expand=True)
            
            # Switch button
            ctk.CTkButton(
                proj_frame,
                text="Switch",
                width=80,
                command=lambda p=project: self.do_switch_project(p, selector)
            ).pack(side="right", padx=5)
        
        # Close button
        ctk.CTkButton(
            selector,
            text="Cancel",
            command=selector.destroy
        ).pack(pady=10)
    
    def do_switch_project(self, project, window):
        """Actually switch to selected project"""
        project_path = project.get('path', '')
        if project_path:
            self.log(f"Switching to project: {project.get('name', 'Unknown')}")
            self.log(f"Path: {project_path}")
            # Change directory and update status
            try:
                os.chdir(project_path)
                self.check_project_status()
                window.destroy()
                self.log("Project switched successfully!")
            except Exception as e:
                self.log(f"Error switching project: {str(e)}", error=True)
    
    def toggle_watch(self):
        """Toggle file watching"""
        # Check current watch status
        result = self.run_command(["watch", "status"])
        
        if result and "running" in result.stdout:
            self.log("Stopping file watcher...")
            self.run_command(["watch", "stop"])
        else:
            self.log("Starting file watcher...")
            self.run_command(["watch", "start", "--daemon"])
    
    def settings_menu(self):
        """Show settings menu with common operations"""
        # Create settings window
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("ClaudeSync Settings")
        settings_window.geometry("400x500")
        settings_window.transient(self.root)
        
        # Title
        ctk.CTkLabel(
            settings_window, 
            text="Quick Settings", 
            font=("Arial", 16, "bold")
        ).pack(pady=10)
        
        # Settings frame
        settings_frame = ctk.CTkFrame(settings_window)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # File size setting
        size_frame = ctk.CTkFrame(settings_frame)
        size_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(size_frame, text="Max File Size (bytes):").pack(side="left", padx=5)
        ctk.CTkButton(
            size_frame, text="Set", width=60,
            command=lambda: self.set_config_value("max_file_size", "number")
        ).pack(side="right", padx=5)
        
        # Compression setting
        comp_frame = ctk.CTkFrame(settings_frame)
        comp_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(comp_frame, text="Compression:").pack(side="left", padx=5)
        comp_var = ctk.StringVar(value="none")
        ctk.CTkOptionMenu(
            comp_frame, 
            values=["none", "zlib", "brotli", "bz2", "lzma"],
            variable=comp_var,
            command=lambda v: self.run_command(["config", "set", "compression_algorithm", v])
        ).pack(side="right", padx=5)
        
        # Two-way sync toggle
        sync_frame = ctk.CTkFrame(settings_frame)
        sync_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(sync_frame, text="Two-way Sync:").pack(side="left", padx=5)
        sync_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            sync_frame, 
            variable=sync_var,
            command=lambda: self.run_command(["config", "set", "two_way_sync", str(sync_var.get()).lower()])
        ).pack(side="right", padx=5)
        
        # Prune remote files toggle
        prune_frame = ctk.CTkFrame(settings_frame)
        prune_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(prune_frame, text="Prune Remote Files:").pack(side="left", padx=5)
        prune_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            prune_frame, 
            variable=prune_var,
            command=lambda: self.run_command(["config", "set", "prune_remote_files", str(prune_var.get()).lower()])
        ).pack(side="right", padx=5)
        
        # Log level setting
        log_frame = ctk.CTkFrame(settings_frame)
        log_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(log_frame, text="Log Level:").pack(side="left", padx=5)
        log_var = ctk.StringVar(value="INFO")
        ctk.CTkOptionMenu(
            log_frame,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=log_var,
            command=lambda v: self.run_command(["config", "set", "log_level", v])
        ).pack(side="right", padx=5)
        
        # Workspace root setting
        ws_frame = ctk.CTkFrame(settings_frame)
        ws_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(ws_frame, text="Workspace Root:").pack(side="left", padx=5)
        ctk.CTkButton(
            ws_frame, text="Browse", width=80,
            command=self.set_workspace_root
        ).pack(side="right", padx=5)
        
        # Show all config button
        ctk.CTkButton(
            settings_frame, text="Show All Settings",
            command=lambda: self.show_settings()
        ).pack(pady=10)
        
        # Close button
        ctk.CTkButton(
            settings_window, text="Close",
            command=settings_window.destroy
        ).pack(pady=10)
    
    def set_config_value(self, key, value_type="string"):
        """Set a configuration value"""
        if value_type == "number":
            value = simpledialog.askstring("Set Configuration", f"Enter value for {key}:")
            if value and value.isdigit():
                self.run_command(["config", "set", key, value])
        else:
            value = simpledialog.askstring("Set Configuration", f"Enter value for {key}:")
            if value:
                self.run_command(["config", "set", key, value])
    
    def set_workspace_root(self):
        """Set workspace root directory"""
        directory = filedialog.askdirectory(title="Select Workspace Root")
        if directory:
            self.run_command(["workspace", "set-root", directory])
            self.log(f"Workspace root set to: {directory}")
            # Refresh workspace status
            self.check_workspace_status()
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-p>', lambda e: self.push_files())
        self.root.bind('<Control-l>', lambda e: self.pull_files())
        self.root.bind('<Control-s>', lambda e: self.sync_files())
        self.root.bind('<Control-w>', lambda e: self.workspace_menu())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-k>', lambda e: self.clear_terminal())
        self.root.bind('<F5>', lambda e: self.check_auth())
        
        # Add shortcuts info to terminal
        self.log("Keyboard Shortcuts: Ctrl+P (Push), Ctrl+L (Pull), Ctrl+S (Sync), Ctrl+W (Workspace)")
        self.log("                   Ctrl+K (Clear), F5 (Refresh), Ctrl+Q (Quit)\n")
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def main():
    """Launch the simple GUI"""
    app = SimpleSyncGUI()
    app.run()


if __name__ == "__main__":
    main()
