"""
ClaudeSync GUI - Sync View
"""
import customtkinter as ctk
from tkinter import messagebox
import subprocess
import threading
import queue
import sys
from pathlib import Path
from typing import Optional


class SyncView:
    def __init__(self, parent_frame, gui_instance):
        self.parent = parent_frame
        self.gui = gui_instance
        self.sync_thread = None
        self.output_queue = queue.Queue()
        self.is_syncing = False
        
    def show(self):
        """Display the sync view"""
        # Clear parent frame
        for widget in self.parent.winfo_children():
            widget.destroy()
            
        # Title
        title = ctk.CTkLabel(
            self.parent,
            text="Sync Operations",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(pady=(20, 10))
        
        # Check if in project directory
        if not self.check_project_directory():
            no_project_label = ctk.CTkLabel(
                self.parent,
                text="No ClaudeSync project found in current directory.\nPlease navigate to a project directory or create a new project.",
                font=ctk.CTkFont(size=14),
                text_color="red"
            )
            no_project_label.pack(pady=50)
            return
        
        # Project info
        self.show_project_info()
        
        # Sync options frame
        options_frame = ctk.CTkFrame(self.parent)
        options_frame.pack(pady=20, padx=20, fill="x")
        
        options_label = ctk.CTkLabel(
            options_frame,
            text="Sync Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        options_label.pack(pady=(10, 5))
        
        # Category selection
        category_frame = ctk.CTkFrame(options_frame)
        category_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(category_frame, text="File Category:").pack(side="left", padx=(0, 10))
        
        self.category_var = ctk.StringVar(value="all_files")
        self.category_menu = ctk.CTkOptionMenu(
            category_frame,
            values=["all_files", "all_source_code", "production_code", "test_code", "build_config"],
            variable=self.category_var
        )
        self.category_menu.pack(side="left")
        
        # Sync type selection
        sync_type_frame = ctk.CTkFrame(options_frame)
        sync_type_frame.pack(pady=10, padx=20, fill="x")
        
        self.sync_type_var = ctk.StringVar(value="push")
        
        push_radio = ctk.CTkRadioButton(
            sync_type_frame,
            text="Push (Upload only)",
            variable=self.sync_type_var,
            value="push"
        )
        push_radio.pack(side="left", padx=10)
        
        pull_radio = ctk.CTkRadioButton(
            sync_type_frame,
            text="Pull (Download only)",
            variable=self.sync_type_var,
            value="pull"
        )
        pull_radio.pack(side="left", padx=10)
        
        sync_radio = ctk.CTkRadioButton(
            sync_type_frame,
            text="Sync (Two-way)",
            variable=self.sync_type_var,
            value="sync"
        )
        sync_radio.pack(side="left", padx=10)
        
        # Additional options
        self.dry_run_var = ctk.BooleanVar(value=False)
        dry_run_check = ctk.CTkCheckBox(
            options_frame,
            text="Dry run (preview changes only)",
            variable=self.dry_run_var
        )
        dry_run_check.pack(pady=5)
        
        # Action buttons
        action_frame = ctk.CTkFrame(self.parent)
        action_frame.pack(pady=20)
        
        self.sync_button = ctk.CTkButton(
            action_frame,
            text="Start Sync",
            command=self.start_sync,
            width=150,
            height=40
        )
        self.sync_button.pack(side="left", padx=10)
        
        self.cancel_button = ctk.CTkButton(
            action_frame,
            text="Cancel",
            command=self.cancel_sync,
            width=100,
            height=40,
            fg_color="red",
            state="disabled"
        )
        self.cancel_button.pack(side="left", padx=10)
        
        # Progress frame
        progress_frame = ctk.CTkFrame(self.parent)
        progress_frame.pack(pady=10, padx=20, fill="x")
        
        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready to sync",
            font=ctk.CTkFont(size=12)
        )
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        # Output text box
        output_label = ctk.CTkLabel(
            self.parent,
            text="Sync Output",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        output_label.pack(pady=(10, 5))
        
        self.output_text = ctk.CTkTextbox(
            self.parent,
            width=600,
            height=200
        )
        self.output_text.pack(pady=10, padx=20, fill="both", expand=True)
        
    def check_project_directory(self):
        """Check if current directory is a ClaudeSync project"""
        config_file = Path.cwd() / ".claudesync" / "config.local.json"
        return config_file.exists()
    
    def show_project_info(self):
        """Show current project information"""
        try:
            config_file = Path.cwd() / ".claudesync" / "config.local.json"
            if config_file.exists():
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    
                project_info_frame = ctk.CTkFrame(self.parent)
                project_info_frame.pack(pady=10, padx=20, fill="x")
                
                project_name = config.get('active_project_name', 'Unknown')
                project_path = config.get('local_path', str(Path.cwd()))
                
                info_label = ctk.CTkLabel(
                    project_info_frame,
                    text=f"Project: {project_name}\nPath: {project_path}",
                    font=ctk.CTkFont(size=12),
                    justify="left"
                )
                info_label.pack(pady=10)
                
        except Exception as e:
            print(f"Error reading project info: {e}")
    
    def start_sync(self):
        """Start the sync operation"""
        if self.is_syncing:
            return
            
        self.is_syncing = True
        self.sync_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting sync...")
        
        # Build command
        sync_type = self.sync_type_var.get()
        category = self.category_var.get()
        dry_run = self.dry_run_var.get()
        
        cmd = [sync_type]
        
        if category != "all_files":
            cmd.extend(["--category", category])
            
        if dry_run:
            cmd.append("--dry-run")
        
        # Start sync in thread
        self.sync_thread = threading.Thread(
            target=self.run_sync,
            args=(cmd,),
            daemon=True
        )
        self.sync_thread.start()
        
        # Start monitoring output
        self.gui.root.after(100, self.check_output)
    
    def run_sync(self, cmd):
        """Run sync command in thread"""
        try:
            # Use Popen for real-time output
            process = subprocess.Popen(
                [sys.executable, "-m", "claudesync.cli.main"] + cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output line by line
            for line in process.stdout:
                self.output_queue.put(("output", line))
            
            process.wait()
            
            if process.returncode == 0:
                self.output_queue.put(("complete", "Sync completed successfully!"))
            else:
                self.output_queue.put(("error", f"Sync failed with code {process.returncode}"))
                
        except Exception as e:
            self.output_queue.put(("error", f"Error: {str(e)}"))
        finally:
            self.output_queue.put(("done", None))
    
    def check_output(self):
        """Check for output from sync thread"""
        try:
            while True:
                msg_type, content = self.output_queue.get_nowait()
                
                if msg_type == "output":
                    self.output_text.insert("end", content)
                    self.output_text.see("end")
                    
                    # Update progress based on output
                    if "Uploading" in content or "Downloading" in content:
                        self.progress_label.configure(text=content.strip())
                        # Simple progress animation
                        current = self.progress_bar.get()
                        self.progress_bar.set((current + 0.1) % 1.0)
                        
                elif msg_type == "complete":
                    self.progress_label.configure(text=content, text_color="green")
                    self.progress_bar.set(1.0)
                    messagebox.showinfo("Success", content)
                    
                elif msg_type == "error":
                    self.progress_label.configure(text=content, text_color="red")
                    messagebox.showerror("Error", content)
                    
                elif msg_type == "done":
                    self.is_syncing = False
                    self.sync_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    return
                    
        except queue.Empty:
            pass
            
        # Continue checking
        if self.is_syncing:
            self.gui.root.after(100, self.check_output)
    
    def cancel_sync(self):
        """Cancel the sync operation"""
        if hasattr(self, 'sync_thread') and self.sync_thread and self.sync_thread.is_alive():
            # Set cancel flag if sync manager supports it
            self.cancel_requested = True
            self.output_queue.put(("info", "Cancellation requested..."))
            # Note: Actual cancellation depends on sync_thread checking self.cancel_requested
        self.output_queue.put(("error", "Sync cancelled by user"))
        self.output_queue.put(("done", None))
