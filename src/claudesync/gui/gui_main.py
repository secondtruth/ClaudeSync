#!/usr/bin/env python3
"""
ClaudeSync GUI - Main entry point
Ensures correct command structure for v3 (csync sync push/pull/sync)
"""

import os
import sys
import json
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, List
import logging

# Check for GUI dependencies
try:
    import customtkinter as ctk
    from tkinter import messagebox, filedialog, ttk
except ImportError:
    print("GUI dependencies not installed. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk
    from tkinter import messagebox, filedialog, ttk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ClaudeSyncGUI:
    """Main GUI application for ClaudeSync v3."""
    
    # Correct command mappings for v3
    COMMANDS = {
        'push': ['csync', 'sync', 'push'],
        'pull': ['csync', 'sync', 'pull'],
        'sync': ['csync', 'sync', 'sync'],
        'auth_login': ['csync', 'auth', 'login'],
        'auth_logout': ['csync', 'auth', 'logout'],
        'org_set': ['csync', 'org', 'set'],
        'org_list': ['csync', 'org', 'ls'],
        'project_create': ['csync', 'project', 'create'],
        'project_list': ['csync', 'project', 'ls'],
        'project_set': ['csync', 'project', 'set'],
        'workspace_sync': ['csync', 'workspace', 'sync-all'],
        'workspace_list': ['csync', 'workspace', 'list'],
        'workspace_clone': ['csync', 'workspace', 'clone'],
        'instructions_push': ['csync', 'project', 'instructions', 'push'],
        'instructions_pull': ['csync', 'project', 'instructions', 'pull'],
    }
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync v3 - GUI")
        self.root.geometry("1200x800")
        
        # State
        self.current_project = None
        self.current_org = None
        self.authenticated = False
        
        # Setup UI
        self.setup_ui()
        self.check_authentication()
        
    def setup_ui(self):
        """Setup the main UI layout."""
        # Main container
        main_container = ctk.CTkFrame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left sidebar
        sidebar = ctk.CTkFrame(main_container, width=250)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)
        
        # Logo/Title
        title_label = ctk.CTkLabel(
            sidebar, 
            text="ClaudeSync v3", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=20)
        
        # Auth status
        self.auth_status = ctk.CTkLabel(
            sidebar,
            text="⚠️ Not Authenticated",
            font=ctk.CTkFont(size=12)
        )
        self.auth_status.pack(pady=(0, 20))
        
        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("🔐 Authentication", self.show_auth_view),
            ("🏢 Organizations", self.show_org_view),
            ("📁 Projects", self.show_project_view),
            ("🔄 Sync", self.show_sync_view),
            ("📝 Instructions", self.show_instructions_view),
            ("🌐 Workspace", self.show_workspace_view),
            ("⚙️ Settings", self.show_settings_view),
        ]
        
        for text, command in nav_items:
            btn = ctk.CTkButton(
                sidebar,
                text=text,
                command=command,
                height=40,
                anchor="w"
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[text] = btn
        
        # Main content area
        self.content_area = ctk.CTkFrame(main_container)
        self.content_area.pack(side="right", fill="both", expand=True)
        
        # Status bar
        self.status_bar = ctk.CTkLabel(
            self.root,
            text="Ready",
            anchor="w",
            height=30
        )
        self.status_bar.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        
        # Start with sync view
        self.show_sync_view()
    
    def check_authentication(self):
        """Check if user is authenticated."""
        try:
            # Check auth status
            result = subprocess.run(
                self.COMMANDS['org_list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and "Organization" in result.stdout:
                self.authenticated = True
                self.auth_status.configure(text="✅ Authenticated")
                self.update_status("Authenticated successfully")
                
                # Try to get current org from output
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if "Active:" in line:
                        self.current_org = line.split("Active:")[-1].strip()
                        break
            else:
                self.authenticated = False
                self.auth_status.configure(text="⚠️ Not Authenticated")
                
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            self.authenticated = False
    
    def show_sync_view(self):
        """Show the sync operations view."""
        self.clear_content()
        
        # Title
        title = ctk.CTkLabel(
            self.content_area,
            text="File Synchronization",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        if not self.authenticated:
            warn_label = ctk.CTkLabel(
                self.content_area,
                text="Please authenticate first",
                text_color="red"
            )
            warn_label.pack(pady=20)
            return
        
        # Current project info
        if self.current_project:
            proj_label = ctk.CTkLabel(
                self.content_area,
                text=f"Current Project: {self.current_project}",
                font=ctk.CTkFont(size=14)
            )
            proj_label.pack(pady=10)
        
        # Sync buttons frame
        sync_frame = ctk.CTkFrame(self.content_area)
        sync_frame.pack(pady=20)
        
        # Push button
        push_btn = ctk.CTkButton(
            sync_frame,
            text="⬆️ Push to Claude",
            command=lambda: self.run_sync_command('push'),
            width=200,
            height=50,
            font=ctk.CTkFont(size=16)
        )
        push_btn.grid(row=0, column=0, padx=10, pady=10)
        
        # Pull button
        pull_btn = ctk.CTkButton(
            sync_frame,
            text="⬇️ Pull from Claude",
            command=lambda: self.run_sync_command('pull'),
            width=200,
            height=50,
            font=ctk.CTkFont(size=16)
        )
        pull_btn.grid(row=0, column=1, padx=10, pady=10)
        
        # Bidirectional sync button
        sync_btn = ctk.CTkButton(
            sync_frame,
            text="🔄 Bidirectional Sync",
            command=lambda: self.run_sync_command('sync'),
            width=200,
            height=50,
            font=ctk.CTkFont(size=16)
        )
        sync_btn.grid(row=1, column=0, columnspan=2, padx=10, pady=10)
        
        # Options frame
        options_frame = ctk.CTkFrame(self.content_area)
        options_frame.pack(pady=20)
        
        # Conflict strategy
        conflict_label = ctk.CTkLabel(options_frame, text="Conflict Strategy:")
        conflict_label.grid(row=0, column=0, padx=10, pady=5)
        
        self.conflict_var = ctk.StringVar(value="prompt")
        conflict_menu = ctk.CTkOptionMenu(
            options_frame,
            values=["prompt", "local-wins", "remote-wins"],
            variable=self.conflict_var
        )
        conflict_menu.grid(row=0, column=1, padx=10, pady=5)
        
        # Dry run option
        self.dry_run_var = ctk.BooleanVar(value=False)
        dry_run_check = ctk.CTkCheckBox(
            options_frame,
            text="Dry Run (Preview Only)",
            variable=self.dry_run_var
        )
        dry_run_check.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        # Output area
        output_label = ctk.CTkLabel(
            self.content_area,
            text="Output:",
            anchor="w"
        )
        output_label.pack(fill="x", padx=20, pady=(20, 5))
        
        self.output_text = ctk.CTkTextbox(
            self.content_area,
            height=300
        )
        self.output_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    def run_sync_command(self, command_type: str):
        """Run a sync command with proper v3 structure."""
        if not self.current_project:
            messagebox.showwarning("No Project", "Please select a project first")
            return
        
        # Build command
        cmd = self.COMMANDS[command_type].copy()
        
        # Add options
        if command_type == 'sync':
            cmd.extend(['--conflict-strategy', self.conflict_var.get()])
        
        if self.dry_run_var.get():
            cmd.append('--dry-run')
        
        # Run in thread to avoid blocking UI
        def run_command():
            try:
                self.update_status(f"Running {command_type}...")
                self.output_text.delete("1.0", "end")
                self.output_text.insert("1.0", f"Executing: {' '.join(cmd)}\n\n")
                
                # Run command
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Stream output
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.root.after(0, self.output_text.insert, "end", line)
                        self.root.after(0, self.output_text.see, "end")
                
                process.wait()
                
                if process.returncode == 0:
                    self.update_status(f"✅ {command_type} completed successfully")
                else:
                    self.update_status(f"❌ {command_type} failed with code {process.returncode}")
                    
            except Exception as e:
                self.update_status(f"❌ Error: {str(e)}")
                self.output_text.insert("end", f"\nError: {str(e)}")
        
        thread = threading.Thread(target=run_command, daemon=True)
        thread.start()
    
    def show_workspace_view(self):
        """Show workspace management view."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Workspace Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        if not self.authenticated:
            warn_label = ctk.CTkLabel(
                self.content_area,
                text="Please authenticate first",
                text_color="red"
            )
            warn_label.pack(pady=20)
            return
        
        # Workspace buttons
        btn_frame = ctk.CTkFrame(self.content_area)
        btn_frame.pack(pady=20)
        
        # List projects button
        list_btn = ctk.CTkButton(
            btn_frame,
            text="📋 List All Projects",
            command=self.list_workspace_projects,
            width=200,
            height=40
        )
        list_btn.grid(row=0, column=0, padx=10, pady=5)
        
        # Clone all button
        clone_btn = ctk.CTkButton(
            btn_frame,
            text="⬇️ Clone All Remote",
            command=self.clone_all_projects,
            width=200,
            height=40
        )
        clone_btn.grid(row=0, column=1, padx=10, pady=5)
        
        # Sync all button
        sync_all_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Sync All Projects",
            command=self.sync_all_projects,
            width=200,
            height=40
        )
        sync_all_btn.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        # Projects list
        list_label = ctk.CTkLabel(
            self.content_area,
            text="Projects in Workspace:",
            anchor="w"
        )
        list_label.pack(fill="x", padx=20, pady=(20, 5))
        
        self.projects_text = ctk.CTkTextbox(
            self.content_area,
            height=400
        )
        self.projects_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    def sync_all_projects(self):
        """Sync all workspace projects using correct v3 commands."""
        cmd = self.COMMANDS['workspace_sync'].copy()
        cmd.append('--dry-run')  # Safety first
        
        def run_sync():
            try:
                self.update_status("Syncing all workspace projects...")
                self.projects_text.delete("1.0", "end")
                self.projects_text.insert("1.0", f"Executing: {' '.join(cmd)}\n\n")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.root.after(0, self.projects_text.insert, "end", line)
                        self.root.after(0, self.projects_text.see, "end")
                
                process.wait()
                
                if process.returncode == 0:
                    self.update_status("✅ Workspace sync completed")
                    
                    # Ask if user wants to run actual sync
                    if messagebox.askyesno("Dry Run Complete", "Dry run complete. Run actual sync?"):
                        # Remove --dry-run and run again
                        actual_cmd = [c for c in cmd if c != '--dry-run']
                        subprocess.Popen(actual_cmd)
                else:
                    self.update_status(f"❌ Workspace sync failed")
                    
            except Exception as e:
                self.update_status(f"❌ Error: {str(e)}")
        
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
    
    def show_auth_view(self):
        """Show authentication view."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Authentication",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        if self.authenticated:
            status_label = ctk.CTkLabel(
                self.content_area,
                text="✅ You are authenticated",
                font=ctk.CTkFont(size=16),
                text_color="green"
            )
            status_label.pack(pady=20)
            
            logout_btn = ctk.CTkButton(
                self.content_area,
                text="Logout",
                command=self.logout,
                width=200,
                height=40
            )
            logout_btn.pack(pady=10)
        else:
            status_label = ctk.CTkLabel(
                self.content_area,
                text="⚠️ Not authenticated",
                font=ctk.CTkFont(size=16),
                text_color="orange"
            )
            status_label.pack(pady=20)
            
            login_btn = ctk.CTkButton(
                self.content_area,
                text="Login to Claude.ai",
                command=self.login,
                width=200,
                height=40
            )
            login_btn.pack(pady=10)
            
            # Instructions
            instructions = ctk.CTkLabel(
                self.content_area,
                text="1. Click Login\n2. Get session key from Claude.ai\n3. Paste when prompted",
                justify="left"
            )
            instructions.pack(pady=20)
    
    def login(self):
        """Run login command."""
        try:
            # Run login command
            result = subprocess.run(
                self.COMMANDS['auth_login'],
                capture_output=True,
                text=True,
                input="\n",  # Auto-approve
                timeout=60
            )
            
            if "Successfully authenticated" in result.stdout:
                self.authenticated = True
                self.auth_status.configure(text="✅ Authenticated")
                self.update_status("Login successful!")
                self.show_org_view()
            else:
                messagebox.showerror("Login Failed", "Authentication failed. Check your session key.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {str(e)}")
    
    def logout(self):
        """Run logout command."""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to logout?"):
            try:
                subprocess.run(self.COMMANDS['auth_logout'])
                self.authenticated = False
                self.auth_status.configure(text="⚠️ Not Authenticated")
                self.update_status("Logged out")
                self.show_auth_view()
            except Exception as e:
                messagebox.showerror("Error", f"Logout failed: {str(e)}")
    
    def show_org_view(self):
        """Show organization management view."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Organization Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Implementation continues...
    
    def show_project_view(self):
        """Show project management view."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Project Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Implementation continues...
    
    def show_instructions_view(self):
        """Show project instructions management."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Project Instructions",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Implementation continues...
    
    def show_settings_view(self):
        """Show settings view."""
        self.clear_content()
        
        title = ctk.CTkLabel(
            self.content_area,
            text="Settings",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Implementation continues...
    
    def list_workspace_projects(self):
        """List all workspace projects."""
        cmd = self.COMMANDS['workspace_list']
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            self.projects_text.delete("1.0", "end")
            self.projects_text.insert("1.0", result.stdout)
            
            if result.returncode == 0:
                self.update_status("✅ Projects listed")
            else:
                self.update_status("❌ Failed to list projects")
                
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}")
    
    def clone_all_projects(self):
        """Clone all remote projects."""
        if messagebox.askyesno("Clone All", "Clone all remote projects to local workspace?"):
            cmd = self.COMMANDS['workspace_clone']
            
            def run_clone():
                try:
                    self.update_status("Cloning all remote projects...")
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    self.projects_text.delete("1.0", "end")
                    
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            self.root.after(0, self.projects_text.insert, "end", line)
                            self.root.after(0, self.projects_text.see, "end")
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        self.update_status("✅ Projects cloned successfully")
                    else:
                        self.update_status("❌ Clone failed")
                        
                except Exception as e:
                    self.update_status(f"❌ Error: {str(e)}")
            
            thread = threading.Thread(target=run_clone, daemon=True)
            thread.start()
    
    def clear_content(self):
        """Clear the content area."""
        for widget in self.content_area.winfo_children():
            widget.destroy()
    
    def update_status(self, message: str):
        """Update status bar."""
        self.status_bar.configure(text=message)
        logger.info(message)
    
    def run(self):
        """Start the GUI."""
        self.root.mainloop()


def main():
    """Launch the GUI."""
    app = ClaudeSyncGUI()
    app.run()


if __name__ == "__main__":
    main()