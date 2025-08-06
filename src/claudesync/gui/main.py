"""
ClaudeSync GUI - Main Application Window
"""
import customtkinter as ctk
import os
import sys
from pathlib import Path
import subprocess
import json
from typing import Optional
import webbrowser
import threading
import queue
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from claudesync.configmanager.file_config_manager import FileConfigManager
from claudesync.exceptions import ConfigurationError
from claudesync.gui.views import ProjectsView, SyncView, WorkspaceView, SettingsView
from claudesync.gui.auth_handler import AuthHandler

# Set appearance
ctk.set_appearance_mode("system")  # Follows Windows theme
ctk.set_default_color_theme("blue")  # Professional look


class ClaudeSyncGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync GUI")
        self.root.geometry("900x700")
        
        # Windows-specific improvements
        if sys.platform == "win32":
            self.root.iconbitmap(default='')  # Default icon for now
            # Center window on screen
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        # Initialize config manager
        self.config_manager = None
        self.current_project = None
        self.current_organization = None
        self.progress_dialog = None
        self.terminal_visible = False
        
        # Initialize authentication handler
        self.auth_handler = AuthHandler()
        
        # Initialize message queue for thread-safe terminal updates
        self.terminal_queue = queue.Queue()
        
        # Create main layout
        self.setup_ui()
        
        # Start processing terminal queue
        self.process_terminal_queue()
        
        # Check auth after UI is set up and run_csync_command is available
        self.root.after(100, self.check_auth_status)
    
    def run_csync_command(self, args, show_in_terminal=True):
        """Run a csync command, trying multiple approaches"""
        # Try different command formats
        commands = [
            ["csync"] + args,
            ["python", "-m", "claudesync.cli.main"] + args,
            [sys.executable, "-m", "claudesync.cli.main"] + args
        ]
        
        result = None
        for cmd in commands:
            try:
                # Log command to terminal (thread-safe)
                if show_in_terminal:
                    self.log_to_terminal(f"$ {' '.join(cmd)}\n", "command")
                
                # Use Popen for real-time output capture
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                stdout_lines = []
                stderr_lines = []
                
                # Read output in real-time
                import select
                if sys.platform != "win32":
                    # Unix-like systems
                    while True:
                        reads = [process.stdout.fileno(), process.stderr.fileno()]
                        ret = select.select(reads, [], [])
                        
                        for fd in ret[0]:
                            if fd == process.stdout.fileno():
                                line = process.stdout.readline()
                                if line:
                                    stdout_lines.append(line)
                                    if show_in_terminal:
                                        self.log_to_terminal(line, "output")
                            if fd == process.stderr.fileno():
                                line = process.stderr.readline()
                                if line:
                                    stderr_lines.append(line)
                                    if show_in_terminal:
                                        self.log_to_terminal(line, "error")
                        
                        if process.poll() is not None:
                            break
                else:
                    # Windows - simpler approach
                    stdout, stderr = process.communicate()
                    stdout_lines = stdout.splitlines(keepends=True) if stdout else []
                    stderr_lines = stderr.splitlines(keepends=True) if stderr else []
                    
                    if show_in_terminal:
                        for line in stdout_lines:
                            self.log_to_terminal(line, "output")
                        for line in stderr_lines:
                            self.log_to_terminal(line, "error")
                
                # Create result object
                class Result:
                    def __init__(self):
                        self.returncode = process.returncode
                        self.stdout = ''.join(stdout_lines)
                        self.stderr = ''.join(stderr_lines)
                
                result = Result()
                
                if result.returncode == 0 or "csync" not in result.stderr.lower():
                    return result
            except Exception as e:
                continue
        
        # If all fail, return last result or create a mock failed result
        if result is None:
            class MockResult:
                returncode = 1
                stdout = ""
                stderr = "Failed to execute command"
            result = MockResult()
        
        return result
    
    def setup_ui(self):
        """Create the main UI layout"""
        # Create main container
        main_container = ctk.CTkFrame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights for main window
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Configure grid for main container
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        
        # Create sidebar
        self.sidebar = ctk.CTkFrame(main_container, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)
        
        # Logo/Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="ClaudeSync", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Navigation buttons
        self.btn_auth = ctk.CTkButton(
            self.sidebar, 
            text="Authentication", 
            command=self.show_auth_view
        )
        self.btn_auth.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_projects = ctk.CTkButton(
            self.sidebar, 
            text="Projects", 
            command=self.show_projects_view
        )
        self.btn_projects.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_sync = ctk.CTkButton(
            self.sidebar, 
            text="Sync", 
            command=self.show_sync_view
        )
        self.btn_sync.grid(row=3, column=0, padx=20, pady=10)
        
        self.btn_workspace = ctk.CTkButton(
            self.sidebar, 
            text="Workspace", 
            command=self.show_workspace_view
        )
        self.btn_workspace.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_settings = ctk.CTkButton(
            self.sidebar, 
            text="Settings", 
            command=self.show_settings_view
        )
        self.btn_settings.grid(row=5, column=0, padx=20, pady=10)
        
        # Terminal toggle button
        self.btn_terminal = ctk.CTkButton(
            self.sidebar, 
            text="Terminal ▼", 
            command=self.toggle_terminal,
            fg_color="gray"
        )
        self.btn_terminal.grid(row=6, column=0, padx=20, pady=10)
        
        # Status label at bottom
        self.status_label = ctk.CTkLabel(
            self.sidebar, 
            text="Not authenticated", 
            text_color="gray"
        )
        self.status_label.grid(row=8, column=0, padx=20, pady=(10, 20))
        
        # Main content area with terminal
        self.content_container = ctk.CTkFrame(main_container, corner_radius=0)
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_rowconfigure(0, weight=3)  # Main content gets more space
        self.content_container.grid_rowconfigure(1, weight=1)  # Terminal gets less space
        self.content_container.grid_columnconfigure(0, weight=1)
        
        # Main content frame
        self.main_frame = ctk.CTkFrame(self.content_container, corner_radius=0)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Terminal frame (initially hidden)
        self.terminal_frame = ctk.CTkFrame(self.content_container, corner_radius=0)
        self.terminal_frame.grid(row=1, column=0, sticky="nsew")
        self.terminal_frame.grid_remove()  # Hide initially
        
        # Terminal header
        terminal_header = ctk.CTkFrame(self.terminal_frame)
        terminal_header.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            terminal_header,
            text="Terminal Output",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=10)
        
        clear_btn = ctk.CTkButton(
            terminal_header,
            text="Clear",
            command=self.clear_terminal,
            width=60,
            height=25
        )
        clear_btn.pack(side="right", padx=5)
        
        # Terminal output
        self.terminal_output = ctk.CTkTextbox(
            self.terminal_frame,
            height=150,
            font=ctk.CTkFont(family="Consolas", size=10)
        )
        self.terminal_output.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        # Show auth view by default
        self.show_auth_view()
    
    def check_auth_status(self):
        """Check if user is authenticated"""
        try:
            auth_status = self.auth_handler.get_current_auth_status()
            
            if auth_status.get("authenticated"):
                self.update_status()
                return True
        except Exception as e:
            print(f"Auth check error: {e}")
        
        self.status_label.configure(
            text="✗ Not authenticated", 
            text_color="red"
        )
        return False
    
    def clear_main_frame(self):
        """Clear all widgets from main frame"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
    
    def show_auth_view(self):
        """Show authentication view"""
        self.clear_main_frame()
        
        # Title
        title = ctk.CTkLabel(
            self.main_frame, 
            text="Authentication", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=20)
        
        # Auth status
        auth_frame = ctk.CTkFrame(self.main_frame)
        auth_frame.pack(pady=20, padx=40, fill="x")
        
        status_text = "Checking authentication status..."
        status_label = ctk.CTkLabel(
            auth_frame, 
            text=status_text,
            font=ctk.CTkFont(size=14)
        )
        status_label.pack(pady=20)
        
        # Check auth and update
        is_authenticated = self.check_auth_status()
        if is_authenticated:
            status_label.configure(
                text="✓ You are authenticated with Claude.ai",
                text_color="green"
            )
            
            # Organization info
            org_frame = ctk.CTkFrame(auth_frame)
            org_frame.pack(pady=20, fill="x")
            
            org_label = ctk.CTkLabel(
                org_frame,
                text="Organization:",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            org_label.pack(pady=5)
            
            if self.current_organization:
                org_info = ctk.CTkLabel(
                    org_frame,
                    text=f"{self.current_organization['name']}\nID: {self.current_organization['id']}",
                    font=ctk.CTkFont(size=11)
                )
                org_info.pack(pady=5)
            else:
                # Try to get current org
                result = self.run_csync_command(["organization", "ls"], show_in_terminal=False)
                if result.returncode == 0:
                    no_org_label = ctk.CTkLabel(
                        org_frame,
                        text="No organization selected",
                        font=ctk.CTkFont(size=11),
                        text_color="orange"
                    )
                    no_org_label.pack(pady=5)
            
            # Organization buttons
            org_btn_frame = ctk.CTkFrame(org_frame)
            org_btn_frame.pack(pady=10)
            
            select_org_btn = ctk.CTkButton(
                org_btn_frame,
                text="Select Organization",
                command=self.check_organizations,
                width=150
            )
            select_org_btn.pack(side="left", padx=5)
            
            # Logout button
            logout_btn = ctk.CTkButton(
                auth_frame,
                text="Logout",
                command=self.logout,
                fg_color="red",
                hover_color="darkred"
            )
            logout_btn.pack(pady=20)
        else:
            status_label.configure(
                text="✗ Not authenticated. Please login.",
                text_color="red"
            )
            
            # Login instructions
            instructions = ctk.CTkTextbox(
                auth_frame,
                height=150,
                width=500
            )
            instructions.pack(pady=20, padx=20)
            instructions.insert("1.0", 
                "To authenticate:\n\n"
                "1. Click 'Open Claude.ai' below\n"
                "2. Login to your Claude.ai account\n"
                "3. Get your session key (see instructions)\n"
                "4. Click 'Login with Session Key' and paste it"
            )
            instructions.configure(state="disabled")
            
            # Buttons
            button_frame = ctk.CTkFrame(auth_frame)
            button_frame.pack(pady=10)
            
            open_claude_btn = ctk.CTkButton(
                button_frame,
                text="Open Claude.ai",
                command=lambda: webbrowser.open("https://claude.ai")
            )
            open_claude_btn.pack(side="left", padx=5)
            
            login_btn = ctk.CTkButton(
                button_frame,
                text="Login with Session Key",
                command=self.login_with_key
            )
            login_btn.pack(side="left", padx=5)
    
    def show_projects_view(self):
        """Show projects view"""
        self.clear_main_frame()
        projects_view = ProjectsView(self.main_frame, self)
        projects_view.show()
    
    def show_sync_view(self):
        """Show sync view"""
        self.clear_main_frame()
        sync_view = SyncView(self.main_frame, self)
        sync_view.show()
    
    def show_workspace_view(self):
        """Show workspace view"""
        self.clear_main_frame()
        workspace_view = WorkspaceView(self.main_frame, self)
        workspace_view.show()
    
    def show_settings_view(self):
        """Show settings view"""
        self.clear_main_frame()
        settings_view = SettingsView(self.main_frame, self)
        settings_view.show()
    
    def login_with_key(self):
        """Show dialog to enter session key"""
        dialog = ctk.CTkInputDialog(
            text="Enter your Claude.ai session key:",
            title="Login"
        )
        session_key = dialog.get_input()
        
        if session_key:
            # Show progress dialog
            self.show_progress("Authenticating...", "Please wait while logging in...")
            
            # Run in thread to prevent freezing
            import threading
            thread = threading.Thread(
                target=self._do_login,
                args=(session_key,),
                daemon=True
            )
            thread.start()
    
    def _do_login(self, session_key):
        """Perform login in background thread"""
        try:
            # Use direct authentication
            success, message, data = self.auth_handler.authenticate(session_key)
            
            # Update UI in main thread
            if success:
                self.root.after(0, self.hide_progress)
                self.root.after(0, lambda: self.show_message("Success", message))
                self.root.after(100, self.check_auth_status)
                self.root.after(200, self.show_auth_view)
                
                # If we have organizations, check if we need to set one
                if data.get("organizations"):
                    self.root.after(300, lambda: self.check_organizations(data["organizations"]))
            else:
                self.root.after(0, self.hide_progress)
                self.root.after(0, lambda: self.show_message("Error", message))
        except Exception as e:
            self.root.after(0, self.hide_progress)
            self.root.after(0, lambda: self.show_message("Error", f"Failed to authenticate: {str(e)}"))
    
    def logout(self):
        """Logout from Claude.ai"""
        self.show_progress("Logging out...", "Please wait...")
        
        # Run in thread
        import threading
        thread = threading.Thread(
            target=self._do_logout,
            daemon=True
        )
        thread.start()
    
    def _do_logout(self):
        """Perform logout in background thread"""
        try:
            success, message = self.auth_handler.logout()
            
            if success:
                self.current_organization = None
                self.root.after(0, self.hide_progress)
                self.root.after(0, lambda: self.show_message("Success", message))
                self.root.after(100, self.check_auth_status)
                self.root.after(200, self.show_auth_view)
            else:
                self.root.after(0, self.hide_progress)
                self.root.after(0, lambda: self.show_message("Error", message))
        except Exception as e:
            self.root.after(0, self.hide_progress)
            self.root.after(0, lambda: self.show_message("Error", f"Failed to logout: {str(e)}"))
    
    def show_message(self, title, message):
        """Show a message dialog"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x150")
        
        # Center on parent
        dialog.transient(self.root)
        dialog.grab_set()
        
        label = ctk.CTkLabel(dialog, text=message, wraplength=350)
        label.pack(pady=20)
        
        ok_btn = ctk.CTkButton(
            dialog, 
            text="OK", 
            command=dialog.destroy
        )
        ok_btn.pack(pady=10)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f'+{x}+{y}')
    
    def toggle_terminal(self):
        """Toggle terminal visibility"""
        if self.terminal_visible:
            self.terminal_frame.grid_remove()
            self.btn_terminal.configure(text="Terminal ▼")
            self.terminal_visible = False
            # Give more space to main content
            self.content_container.grid_rowconfigure(0, weight=1)
            self.content_container.grid_rowconfigure(1, weight=0)
        else:
            self.terminal_frame.grid()
            self.btn_terminal.configure(text="Terminal ▲")
            self.terminal_visible = True
            # Share space between main content and terminal
            self.content_container.grid_rowconfigure(0, weight=3)
            self.content_container.grid_rowconfigure(1, weight=1)
    
    def log_to_terminal(self, text, msg_type="output"):
        """Log text to terminal output (thread-safe)"""
        # Add to queue for main thread processing
        self.terminal_queue.put((text, msg_type))
    
    def clear_terminal(self):
        """Clear terminal output"""
        self.terminal_output.delete("1.0", "end")
    
    def process_terminal_queue(self):
        """Process queued terminal messages on main thread"""
        try:
            # Only process if terminal_output exists
            if hasattr(self, 'terminal_output'):
                while True:
                    text, msg_type = self.terminal_queue.get_nowait()
                    
                    # Update terminal on main thread
                    if msg_type == "command":
                        self.terminal_output.insert("end", text, "command")
                        self.terminal_output.tag_config("command", foreground="cyan")
                    elif msg_type == "error":
                        self.terminal_output.insert("end", text, "error")
                        self.terminal_output.tag_config("error", foreground="red")
                    else:
                        self.terminal_output.insert("end", text)
                    
                    self.terminal_output.see("end")
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(50, self.process_terminal_queue)
    
    def show_progress(self, title, message):
        """Show progress dialog"""
        self.progress_dialog = ctk.CTkToplevel(self.root)
        self.progress_dialog.title(title)
        self.progress_dialog.geometry("300x120")
        self.progress_dialog.transient(self.root)
        self.progress_dialog.grab_set()
        
        # Center dialog
        self.progress_dialog.update_idletasks()
        x = (self.progress_dialog.winfo_screenwidth() // 2) - (150)
        y = (self.progress_dialog.winfo_screenheight() // 2) - (60)
        self.progress_dialog.geometry(f'+{x}+{y}')
        
        # Message
        label = ctk.CTkLabel(self.progress_dialog, text=message)
        label.pack(pady=20)
        
        # Progress bar
        progress = ctk.CTkProgressBar(self.progress_dialog, width=250)
        progress.pack(pady=10)
        progress.set(0)
        progress.start()
        
        # Prevent closing
        self.progress_dialog.protocol("WM_DELETE_WINDOW", lambda: None)
    
    def hide_progress(self):
        """Hide progress dialog"""
        if self.progress_dialog:
            self.progress_dialog.destroy()
            self.progress_dialog = None
    
    def check_organizations(self, organizations=None):
        """Check available organizations after login"""
        if organizations is None:
            # Get organizations from auth handler
            auth_status = self.auth_handler.get_current_auth_status()
            organizations = auth_status.get("organizations", [])
        
        if organizations:
            # If only one org, set it automatically
            if len(organizations) == 1:
                self.set_organization(organizations[0])
            else:
                # Show org selection dialog
                self.show_organization_dialog(organizations)
    
    def show_organization_dialog(self, orgs):
        """Show organization selection dialog"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Select Organization")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (200)
        y = (dialog.winfo_screenheight() // 2) - (150)
        dialog.geometry(f'+{x}+{y}')
        
        # Title
        title = ctk.CTkLabel(
            dialog,
            text="Select Organization",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(pady=10)
        
        # Org list
        org_frame = ctk.CTkScrollableFrame(dialog, width=350, height=180)
        org_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        selected_org = ctk.StringVar()
        
        for org in orgs:
            radio = ctk.CTkRadioButton(
                org_frame,
                text=f"{org['name']}",
                variable=selected_org,
                value=org['id']
            )
            radio.pack(pady=5, anchor="w")
            
            # Set first as default
            if not selected_org.get():
                selected_org.set(org['id'])
        
        # Buttons
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(pady=10)
        
        def select_org():
            org_id = selected_org.get()
            if org_id:
                # Find selected org
                for org in orgs:
                    if org['id'] == org_id:
                        self.set_organization(org)
                        break
            dialog.destroy()
        
        select_btn = ctk.CTkButton(
            button_frame,
            text="Select",
            command=select_org
        )
        select_btn.pack(side="left", padx=5)
        
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            fg_color="gray"
        )
        cancel_btn.pack(side="left", padx=5)
    
    def set_organization(self, org):
        """Set the active organization"""
        self.show_progress("Setting Organization", f"Setting {org['name']}...")
        
        # Run in thread
        import threading
        thread = threading.Thread(
            target=self._set_organization_thread,
            args=(org,),
            daemon=True
        )
        thread.start()
    
    def _set_organization_thread(self, org):
        """Set organization in background thread"""
        success, message = self.auth_handler.set_organization(org['id'], org['name'])
        
        if success:
            self.current_organization = org
            self.root.after(0, self.hide_progress)
            self.root.after(0, lambda: self.show_message("Success", message))
            self.root.after(100, self.update_status)
        else:
            self.root.after(0, self.hide_progress)
            self.root.after(0, lambda: self.show_message("Error", message))
            # Update status
            self.root.after(100, self.update_status)
    
    def update_status(self):
        """Update the status label with current auth and org info"""
        auth_status = self.auth_handler.get_current_auth_status()
        
        if auth_status.get("authenticated"):
            status_text = "✓ Authenticated"
            
            # Update current organization
            if auth_status.get("active_organization"):
                self.current_organization = auth_status["active_organization"]
                status_text += f"\n{self.current_organization['name']}"
            
            self.status_label.configure(text=status_text, text_color="green")
        else:
            self.status_label.configure(text="✗ Not authenticated", text_color="red")
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def launch():
    """Entry point for GUI"""
    app = ClaudeSyncGUI()
    app.run()


if __name__ == "__main__":
    launch()
