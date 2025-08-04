"""
ClaudeSync GUI - Projects View
"""
import customtkinter as ctk
from tkinter import messagebox
import subprocess
import json
from typing import List, Dict, Optional
from pathlib import Path


class ProjectsView:
    def __init__(self, parent_frame, gui_instance):
        self.parent = parent_frame
        self.gui = gui_instance
        self.projects = []
        self.selected_project = None
        
    def show(self):
        """Display the projects view"""
        # Clear parent frame
        for widget in self.parent.winfo_children():
            widget.destroy()
            
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Projects",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(20, 10))
        
        # Current project info
        self.project_info_frame = ctk.CTkFrame(self.parent)
        self.project_info_frame.pack(pady=10, padx=20, fill="x")
        
        self.current_project_label = ctk.CTkLabel(
            self.project_info_frame,
            text="Loading current project...",
            font=ctk.CTkFont(size=14)
        )
        self.current_project_label.pack(pady=10)
        
        # Action buttons
        action_frame = ctk.CTkFrame(self.parent)
        action_frame.pack(pady=10)
        
        create_btn = ctk.CTkButton(
            action_frame,
            text="Create New Project",
            command=self.create_project
        )
        create_btn.pack(side="left", padx=5)
        
        refresh_btn = ctk.CTkButton(
            action_frame,
            text="Refresh",
            command=self.refresh_projects
        )
        refresh_btn.pack(side="left", padx=5)
        
        # Projects list frame
        list_frame = ctk.CTkFrame(self.parent)
        list_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # List header
        header = ctk.CTkLabel(
            list_frame,
            text="Available Projects",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.pack(pady=(10, 5))
        
        # Scrollable frame for projects
        self.scrollable_frame = ctk.CTkScrollableFrame(
            list_frame,
            width=500,
            height=300
        )
        self.scrollable_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Load projects
        self.refresh_projects()
        
    def get_current_project(self):
        """Get the current active project"""
        try:
            # Try to read local config
            cwd = Path.cwd()
            config_file = cwd / ".claudesync" / "config.local.json"
            
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    project_name = config.get('active_project_name', 'None')
                    project_id = config.get('active_project_id', '')
                    
                    if project_name != 'None':
                        self.current_project_label.configure(
                            text=f"Current Project: {project_name}\nPath: {cwd}",
                            text_color="green"
                        )
                        return project_id
            
            self.current_project_label.configure(
                text="No project selected in current directory",
                text_color="gray"
            )
            return None
            
        except Exception as e:
            self.current_project_label.configure(
                text=f"Error reading project: {str(e)}",
                text_color="red"
            )
            return None
    
    def refresh_projects(self):
        """Refresh the projects list"""
        # Clear existing project widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Get current project
        current_project_id = self.get_current_project()
        
        # Get projects list
        result = self.gui.run_csync_command(["project", "ls"])
        
        if result.returncode == 0:
            # Parse projects from output
            lines = result.stdout.strip().split('\n')
            self.projects = []
            
            for line in lines:
                if " - " in line and "ID:" in line:
                    # Extract project info
                    parts = line.split(" - ")
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        id_part = parts[1].split("ID:")[1].strip() if "ID:" in parts[1] else ""
                        id_value = id_part.split()[0] if id_part else ""
                        
                        self.projects.append({
                            'name': name,
                            'id': id_value,
                            'full_line': line
                        })
            
            # Display projects
            if self.projects:
                for project in self.projects:
                    self.create_project_widget(project, project['id'] == current_project_id)
            else:
                no_projects_label = ctk.CTkLabel(
                    self.scrollable_frame,
                    text="No projects found. Create one to get started!",
                    text_color="gray"
                )
                no_projects_label.pack(pady=20)
        else:
            error_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=f"Failed to load projects: {result.stderr}",
                text_color="red"
            )
            error_label.pack(pady=20)
    
    def create_project_widget(self, project: Dict, is_current: bool = False):
        """Create a widget for a single project"""
        # Project frame
        project_frame = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color="green" if is_current else "transparent"
        )
        project_frame.pack(pady=5, padx=10, fill="x")
        
        # Project info
        info_frame = ctk.CTkFrame(project_frame)
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        name_label = ctk.CTkLabel(
            info_frame,
            text=project['name'],
            font=ctk.CTkFont(size=14, weight="bold")
        )
        name_label.pack(anchor="w")
        
        id_label = ctk.CTkLabel(
            info_frame,
            text=f"ID: {project['id']}",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        id_label.pack(anchor="w")
        
        if is_current:
            current_label = ctk.CTkLabel(
                info_frame,
                text="✓ Current Project",
                font=ctk.CTkFont(size=10),
                text_color="white" if is_current else "green"
            )
            current_label.pack(anchor="w")
        
        # Action buttons
        button_frame = ctk.CTkFrame(project_frame)
        button_frame.pack(side="right", padx=10)
        
        if not is_current:
            set_btn = ctk.CTkButton(
                button_frame,
                text="Set Active",
                width=80,
                height=25,
                command=lambda: self.set_active_project(project)
            )
            set_btn.pack(side="left", padx=2)
        
        sync_btn = ctk.CTkButton(
            button_frame,
            text="Sync",
            width=60,
            height=25,
            command=lambda: self.sync_project(project)
        )
        sync_btn.pack(side="left", padx=2)
    
    def create_project(self):
        """Create a new project"""
        # Create dialog
        dialog = ctk.CTkToplevel(self.gui.root)
        dialog.title("Create New Project")
        dialog.geometry("400x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')
        
        # Form fields
        ctk.CTkLabel(dialog, text="Create New Project", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Project name
        ctk.CTkLabel(dialog, text="Project Name:").pack(pady=(10, 0))
        name_entry = ctk.CTkEntry(dialog, width=300)
        name_entry.pack(pady=5)
        
        # Description
        ctk.CTkLabel(dialog, text="Description:").pack(pady=(10, 0))
        desc_text = ctk.CTkTextbox(dialog, width=300, height=80)
        desc_text.pack(pady=5)
        
        # Local path
        ctk.CTkLabel(dialog, text="Local Path:").pack(pady=(10, 0))
        path_entry = ctk.CTkEntry(dialog, width=300)
        path_entry.pack(pady=5)
        path_entry.insert(0, str(Path.cwd()))
        
        # Buttons
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(pady=20)
        
        def do_create():
            name = name_entry.get().strip()
            desc = desc_text.get("1.0", "end").strip()
            path = path_entry.get().strip()
            
            if not name:
                messagebox.showerror("Error", "Project name is required")
                return
            
            # Create project
            cmd = ["project", "create", "--name", name]
            if desc:
                cmd.extend(["--description", desc])
            if path and path != str(Path.cwd()):
                cmd.extend(["--local-path", path])
            
            result = self.gui.run_csync_command(cmd)
            
            if result.returncode == 0:
                self.gui.show_message("Success", f"Project '{name}' created successfully!")
                dialog.destroy()
                self.refresh_projects()
            else:
                messagebox.showerror("Error", f"Failed to create project: {result.stderr}")
        
        create_btn = ctk.CTkButton(
            button_frame,
            text="Create",
            command=do_create
        )
        create_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            fg_color="gray"
        )
        cancel_btn.pack(side="left", padx=5)
    
    def set_active_project(self, project: Dict):
        """Set a project as active"""
        # Ask for directory
        from tkinter import filedialog
        directory = filedialog.askdirectory(
            title=f"Select directory for project '{project['name']}'"
        )
        
        if directory:
            # Change to that directory and set project
            import os
            os.chdir(directory)
            
            result = self.gui.run_csync_command(["project", "set"])
            
            if result.returncode == 0:
                self.gui.show_message("Success", f"Project '{project['name']}' set as active in {directory}")
                self.refresh_projects()
            else:
                messagebox.showerror("Error", f"Failed to set project: {result.stderr}")
    
    def sync_project(self, project: Dict):
        """Sync a project (placeholder for now)"""
        self.gui.show_message("Info", f"Sync functionality for '{project['name']}' coming soon!")
