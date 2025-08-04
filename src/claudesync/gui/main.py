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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from claudesync.configmanager.file_config_manager import FileConfigManager
from claudesync.exceptions import ConfigurationError
from claudesync.gui.views import ProjectsView, SyncView, WorkspaceView, SettingsView

# Set appearance
ctk.set_appearance_mode("system")  # Follows Windows theme
ctk.set_default_color_theme("blue")  # Professional look


class ClaudeSyncGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync GUI")
        self.root.geometry("800x600")
        
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
        
        # Create main layout
        self.setup_ui()
        # Check auth after UI is set up and run_csync_command is available
        self.root.after(100, self.check_auth_status)
    
    def run_csync_command(self, args):
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
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    shell=False
                )
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
        # Create sidebar
        self.sidebar = ctk.CTkFrame(self.root, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        
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
        
        # Status label at bottom
        self.status_label = ctk.CTkLabel(
            self.sidebar, 
            text="Not authenticated", 
            text_color="gray"
        )
        self.status_label.grid(row=7, column=0, padx=20, pady=(10, 20))
        
        # Main content area
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        
        # Configure grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
        # Show auth view by default
        self.show_auth_view()
    
    def check_auth_status(self):
        """Check if user is authenticated"""
        try:
            result = self.run_csync_command(["auth", "ls"])
            
            if result and "claude.ai" in result.stdout and "Active" in result.stdout:
                self.status_label.configure(
                    text="✓ Authenticated", 
                    text_color="green"
                )
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
            
            # Logout button
            logout_btn = ctk.CTkButton(
                auth_frame,
                text="Logout",
                command=self.logout,
                fg_color="red",
                hover_color="darkred"
            )
            logout_btn.pack(pady=10)
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
            try:
                # Run csync auth login with session key
                result = self.run_csync_command([
                    "auth", "login", 
                    "--session-key", session_key, 
                    "--auto-approve"
                ])
                
                if result.returncode == 0:
                    self.show_message("Success", "Successfully authenticated!")
                    self.check_auth_status()
                    self.show_auth_view()  # Refresh view
                else:
                    self.show_message("Error", f"Authentication failed: {result.stderr}")
            except Exception as e:
                self.show_message("Error", f"Failed to authenticate: {str(e)}")
    
    def logout(self):
        """Logout from Claude.ai"""
        try:
            result = self.run_csync_command(["auth", "logout"])
            
            if result.returncode == 0:
                self.show_message("Success", "Successfully logged out!")
                self.check_auth_status()
                self.show_auth_view()  # Refresh view
            else:
                self.show_message("Error", f"Logout failed: {result.stderr}")
        except Exception as e:
            self.show_message("Error", f"Failed to logout: {str(e)}")
    
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
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def launch():
    """Entry point for GUI"""
    app = ClaudeSyncGUI()
    app.run()


if __name__ == "__main__":
    launch()
