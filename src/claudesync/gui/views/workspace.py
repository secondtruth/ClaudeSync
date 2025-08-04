"""
ClaudeSync GUI - Workspace View
"""
import customtkinter as ctk
from tkinter import messagebox, filedialog
import subprocess
import threading
import json
from pathlib import Path
from typing import List, Dict


class WorkspaceView:
    def __init__(self, parent_frame, gui_instance):
        self.parent = parent_frame
        self.gui = gui_instance
        self.workspace_path = None
        self.discovered_projects = []
        
    def show(self):
        """Display the workspace view"""
        # Clear parent frame
        for widget in self.parent.winfo_children():
            widget.destroy()
            
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Workspace Management",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(20, 10))
        
        # Description
        desc = ctk.CTkLabel(
            self.parent,
            text="Manage multiple ClaudeSync projects in a workspace",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        desc.pack(pady=(0, 20))
        
        # Workspace selection
        workspace_frame = ctk.CTkFrame(self.parent)
        workspace_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(
            workspace_frame,
            text="Workspace Directory:",
            font=ctk.CTkFont(size=14)
        ).pack(pady=5)
        
        path_frame = ctk.CTkFrame(workspace_frame)
        path_frame.pack(pady=5, fill="x", padx=20)
        
        self.path_label = ctk.CTkLabel(
            path_frame,
            text=str(Path.home() / "Documents" / "ClaudeSync"),
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.path_label.pack(side="left", padx=(0, 10))
        
        browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            command=self.browse_workspace,
            width=80
        )
        browse_btn.pack(side="left")
        
        # Action buttons
        action_frame = ctk.CTkFrame(self.parent)
        action_frame.pack(pady=20)
        
        discover_btn = ctk.CTkButton(
            action_frame,
            text="Discover Projects",
            command=self.discover_projects,
            width=150
        )
        discover_btn.pack(side="left", padx=5)
        
        clone_all_btn = ctk.CTkButton(
            action_frame,
            text="Clone All Projects",
            command=self.clone_all_projects,
            width=150
        )
        clone_all_btn.pack(side="left", padx=5)
        
        sync_all_btn = ctk.CTkButton(
            action_frame,
            text="Sync All Projects",
            command=self.sync_all_projects,
            width=150
        )
        sync_all_btn.pack(side="left", padx=5)
        
        # Projects list
        list_frame = ctk.CTkFrame(self.parent)
        list_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        list_label = ctk.CTkLabel(
            list_frame,
            text="Discovered Projects",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        list_label.pack(pady=(10, 5))
        
        # Scrollable frame for projects
        self.projects_frame = ctk.CTkScrollableFrame(
            list_frame,
            width=600,
            height=250
        )
        self.projects_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.parent,
            text="Select a workspace directory to get started",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.pack(pady=10)
        
    def browse_workspace(self):
        """Browse for workspace directory"""
        directory = filedialog.askdirectory(
            title="Select Workspace Directory",
            initialdir=str(Path.home() / "Documents")
        )
        
        if directory:
            self.workspace_path = Path(directory)
            self.path_label.configure(text=str(self.workspace_path))
            self.status_label.configure(
                text=f"Workspace set to: {self.workspace_path}",
                text_color="green"
            )
            
    def discover_projects(self):
        """Discover all ClaudeSync projects in workspace"""
        if not self.workspace_path:
            self.workspace_path = Path(self.path_label.cget("text"))
            
        if not self.workspace_path.exists():
            messagebox.showerror("Error", "Workspace directory does not exist")
            return
            
        # Clear existing projects
        for widget in self.projects_frame.winfo_children():
            widget.destroy()
            
        self.discovered_projects = []
        self.status_label.configure(text="Discovering projects...", text_color="blue")
        
        # Run discovery in thread
        thread = threading.Thread(target=self._discover_projects_thread, daemon=True)
        thread.start()
        
    def _discover_projects_thread(self):
        """Discover projects in background thread"""
        try:
            # Change to workspace directory
            import os
            original_dir = os.getcwd()
            os.chdir(self.workspace_path)
            
            # Run workspace discover command
            result = self.gui.run_csync_command(["workspace", "discover"])
            
            os.chdir(original_dir)
            
            if result.returncode == 0:
                # Parse discovered projects
                lines = result.stdout.strip().split('\n')
                projects = []
                
                for line in lines:
                    if "Project:" in line and "Path:" in line:
                        # Extract project info
                        parts = line.split(" - ")
                        if len(parts) >= 2:
                            project_name = parts[0].replace("Project:", "").strip()
                            path_part = parts[1].replace("Path:", "").strip() if len(parts) > 1 else ""
                            
                            projects.append({
                                'name': project_name,
                                'path': path_part,
                                'full_path': self.workspace_path / path_part
                            })
                
                # Update UI in main thread
                self.gui.root.after(0, self._update_discovered_projects, projects)
            else:
                self.gui.root.after(0, self._show_error, f"Discovery failed: {result.stderr}")
                
        except Exception as e:
            self.gui.root.after(0, self._show_error, f"Error: {str(e)}")
            
    def _update_discovered_projects(self, projects):
        """Update UI with discovered projects"""
        self.discovered_projects = projects
        
        if projects:
            self.status_label.configure(
                text=f"Found {len(projects)} projects",
                text_color="green"
            )
            
            for project in projects:
                self._create_project_widget(project)
        else:
            self.status_label.configure(
                text="No projects found in workspace",
                text_color="orange"
            )
            
    def _create_project_widget(self, project):
        """Create widget for discovered project"""
        frame = ctk.CTkFrame(self.projects_frame)
        frame.pack(pady=5, padx=10, fill="x")
        
        # Project info
        info_frame = ctk.CTkFrame(frame)
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        name_label = ctk.CTkLabel(
            info_frame,
            text=project['name'],
            font=ctk.CTkFont(size=14, weight="bold")
        )
        name_label.pack(anchor="w")
        
        path_label = ctk.CTkLabel(
            info_frame,
            text=f"Path: {project['path']}",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        path_label.pack(anchor="w")
        
        # Action buttons
        button_frame = ctk.CTkFrame(frame)
        button_frame.pack(side="right", padx=10)
        
        open_btn = ctk.CTkButton(
            button_frame,
            text="Open",
            width=60,
            height=25,
            command=lambda: self._open_project(project)
        )
        open_btn.pack(side="left", padx=2)
        
        sync_btn = ctk.CTkButton(
            button_frame,
            text="Sync",
            width=60,
            height=25,
            command=lambda: self._sync_project(project)
        )
        sync_btn.pack(side="left", padx=2)
        
    def clone_all_projects(self):
        """Clone all remote projects"""
        if not self.workspace_path:
            self.workspace_path = Path(self.path_label.cget("text"))
            
        # Create directory if it doesn't exist
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Confirm action
        if not messagebox.askyesno(
            "Clone All Projects",
            f"This will clone all remote projects to:\n{self.workspace_path}\n\nContinue?"
        ):
            return
            
        self.status_label.configure(text="Cloning all projects...", text_color="blue")
        
        # Run in thread
        thread = threading.Thread(target=self._clone_all_thread, daemon=True)
        thread.start()
        
    def _clone_all_thread(self):
        """Clone all projects in background"""
        try:
            import os
            os.chdir(self.workspace_path)
            
            result = self.gui.run_csync_command(["workspace", "clone"])
            
            if result.returncode == 0:
                # Count cloned projects
                lines = result.stdout.strip().split('\n')
                cloned_count = sum(1 for line in lines if "Created project directory" in line)
                
                self.gui.root.after(
                    0, 
                    lambda: self.status_label.configure(
                        text=f"Successfully cloned {cloned_count} projects",
                        text_color="green"
                    )
                )
                
                # Refresh project list
                self.gui.root.after(100, self.discover_projects)
            else:
                self.gui.root.after(0, self._show_error, f"Clone failed: {result.stderr}")
                
        except Exception as e:
            self.gui.root.after(0, self._show_error, f"Error: {str(e)}")
            
    def sync_all_projects(self):
        """Sync all projects in workspace"""
        if not self.discovered_projects:
            messagebox.showinfo("Info", "No projects discovered. Run 'Discover Projects' first.")
            return
            
        # Confirm action
        if not messagebox.askyesno(
            "Sync All Projects",
            f"This will sync {len(self.discovered_projects)} projects.\n\nContinue?"
        ):
            return
            
        # TODO: Implement batch sync
        messagebox.showinfo("Info", "Batch sync functionality coming soon!")
        
    def _open_project(self, project):
        """Open project directory"""
        import os
        import platform
        
        path = project['full_path']
        if platform.system() == 'Windows':
            os.startfile(path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', path])
        else:  # Linux
            subprocess.Popen(['xdg-open', path])
            
    def _sync_project(self, project):
        """Sync individual project"""
        # TODO: Implement individual project sync
        messagebox.showinfo("Info", f"Sync for '{project['name']}' coming soon!")
        
    def _show_error(self, message):
        """Show error message"""
        self.status_label.configure(text=message, text_color="red")
        messagebox.showerror("Error", message)
