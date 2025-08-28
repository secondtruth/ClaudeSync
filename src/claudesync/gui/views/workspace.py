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
            result = self.gui.run_csync_command(["workspace", "discover"], show_in_terminal=False)
            
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
            
            result = self.gui.run_csync_command(["workspace", "clone"], show_in_terminal=True)
            
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
            
        # Import required modules
        import threading
        from claudesync.syncmanager import SyncManager, SyncDirection
        from claudesync.configmanager import FileConfigManager
        from claudesync.providers import ClaudeAIProvider
        from claudesync.utils import get_local_files
        
        # Create progress window
        progress_window = ctk.CTkToplevel(self.gui.root)
        progress_window.title("Syncing Projects...")
        progress_window.geometry("600x400")
        progress_window.transient(self.gui.root)
        
        # Progress display
        progress_text = ctk.CTkTextbox(progress_window)
        progress_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(progress_window)
        progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        progress_bar.set(0)
        
        # Cancel button
        cancel_event = threading.Event()
        cancel_btn = ctk.CTkButton(
            progress_window,
            text="Cancel",
            command=lambda: cancel_event.set()
        )
        cancel_btn.pack(pady=(0, 10))
        
        def sync_worker():
            """Worker thread for syncing projects"""
            success_count = 0
            error_count = 0
            total = len(self.discovered_projects)
            
            for i, project in enumerate(self.discovered_projects, 1):
                if cancel_event.is_set():
                    break
                    
                project_path = project['full_path']
                project_name = project['name']
                
                # Update progress
                self.gui.root.after(0, lambda n=project_name, idx=i, t=total: progress_text.insert("end", f"\n[{idx}/{t}] Syncing {n}..."))
                self.gui.root.after(0, lambda v=i/total: progress_bar.set(v))
                
                try:
                    # Load project config
                    config_path = os.path.join(project_path, '.claudesync')
                    if not os.path.exists(config_path):
                        raise Exception("No .claudesync directory found")
                        
                    # Initialize config manager
                    os.chdir(project_path)  # Change to project directory
                    project_config = FileConfigManager(config_path)
                    
                    # Get provider
                    session_key = project_config.get_session_key()
                    if not session_key:
                        raise Exception("No session key found")
                    provider = ClaudeAIProvider(session_key)
                    
                    # Get project details
                    org_id = project_config.get("active_organization_id")
                    proj_id = project_config.get("active_project_id")
                    
                    if not org_id or not proj_id:
                        raise Exception("Project not properly configured")
                    
                    # Get files
                    local_files = get_local_files(project_config, project_path)
                    remote_files = provider.list_files(org_id, proj_id)
                    
                    # Initialize sync manager
                    sync_manager = SyncManager(provider, project_config, project_path)
                    
                    # Build and execute sync plan
                    plan = sync_manager.build_plan(
                        direction=SyncDirection.BOTH,
                        dry_run=False,
                        conflict_strategy='local-wins',
                        local_files=local_files,
                        remote_files=remote_files
                    )
                    
                    if plan.total_operations > 0:
                        results = sync_manager.execute_plan(plan)
                        up = results.get('uploaded', 0)
                        down = results.get('downloaded', 0)
                        self.gui.root.after(0, lambda: progress_text.insert("end", f" ✓ ({up} up, {down} down)"))
                    else:
                        self.gui.root.after(0, lambda: progress_text.insert("end", " ✓ (no changes)"))
                        
                    success_count += 1
                    
                except Exception as e:
                    self.gui.root.after(0, lambda err=str(e): progress_text.insert("end", f" ✗ Error: {err}"))
                    error_count += 1
            
            # Final summary
            self.gui.root.after(0, lambda: progress_text.insert("end", f"\n\n{'='*60}\n"))
            self.gui.root.after(0, lambda: progress_text.insert("end", f"Sync Complete: {success_count} successful, {error_count} failed\n"))
            self.gui.root.after(0, lambda: progress_bar.set(1))
            self.gui.root.after(0, lambda: cancel_btn.configure(text="Close", command=progress_window.destroy))
        
        # Start sync in background thread
        thread = threading.Thread(target=sync_worker, daemon=True)
        thread.start()
        
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
        from claudesync.syncmanager import SyncManager, SyncDirection
        from claudesync.configmanager import FileConfigManager
        from claudesync.providers import ClaudeAIProvider
        from claudesync.utils import get_local_files
        
        project_path = project['full_path']
        project_name = project['name']
        
        try:
            # Initialize config and provider
            os.chdir(project_path)
            config_path = os.path.join(project_path, '.claudesync')
            project_config = FileConfigManager(config_path)
            
            session_key = project_config.get_session_key()
            if not session_key:
                messagebox.showerror("Error", f"No session key found for {project_name}")
                return
                
            provider = ClaudeAIProvider(session_key)
            
            # Get project details
            org_id = project_config.get("active_organization_id")
            proj_id = project_config.get("active_project_id")
            
            # Get files and sync
            local_files = get_local_files(project_config, project_path)
            remote_files = provider.list_files(org_id, proj_id)
            
            sync_manager = SyncManager(provider, project_config, project_path)
            plan = sync_manager.build_plan(
                direction=SyncDirection.BOTH,
                dry_run=False,
                conflict_strategy='local-wins',
                local_files=local_files,
                remote_files=remote_files
            )
            
            if plan.total_operations > 0:
                results = sync_manager.execute_plan(plan)
                messagebox.showinfo("Success", 
                    f"Sync complete for '{project_name}':\n"
                    f"Uploaded: {results.get('uploaded', 0)} files\n"
                    f"Downloaded: {results.get('downloaded', 0)} files")
            else:
                messagebox.showinfo("Info", f"No changes needed for '{project_name}'")
                
        except Exception as e:
            messagebox.showerror("Error", f"Sync failed for '{project_name}': {str(e)}")
        
    def _show_error(self, message):
        """Show error message"""
        self.status_label.configure(text=message, text_color="red")
        messagebox.showerror("Error", message)
