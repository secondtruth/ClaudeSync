"""
Simplified test GUI for authentication debugging
"""
import customtkinter as ctk
import sys
from pathlib import Path
import threading
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from claudesync.gui.auth_handler import AuthHandler


class SimpleAuthTest:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ClaudeSync Auth Test")
        self.root.geometry("400x300")
        
        self.auth_handler = AuthHandler()
        self.setup_ui()
        
    def setup_ui(self):
        # Title
        title = ctk.CTkLabel(self.root, text="Authentication Test", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Status
        self.status_label = ctk.CTkLabel(self.root, text="Checking status...")
        self.status_label.pack(pady=5)
        
        # Session key entry
        self.key_entry = ctk.CTkEntry(self.root, width=300, placeholder_text="Paste session key here")
        self.key_entry.pack(pady=10)
        
        # Buttons
        self.auth_btn = ctk.CTkButton(self.root, text="Authenticate", command=self.authenticate)
        self.auth_btn.pack(pady=5)
        
        self.logout_btn = ctk.CTkButton(self.root, text="Logout", command=self.logout)
        self.logout_btn.pack(pady=5)
        
        # Output
        self.output = ctk.CTkTextbox(self.root, width=350, height=100)
        self.output.pack(pady=10)
        
        # Check initial status
        self.check_status()
        
    def log(self, message):
        """Add message to output"""
        self.output.insert("end", f"{message}\n")
        self.output.see("end")
        
    def check_status(self):
        """Check current auth status"""
        try:
            status = self.auth_handler.get_current_auth_status()
            if status.get("authenticated"):
                self.status_label.configure(text="✓ Authenticated", text_color="green")
                self.log(f"Authenticated with {len(status.get('organizations', []))} orgs")
            else:
                self.status_label.configure(text="✗ Not authenticated", text_color="red")
                self.log("Not authenticated")
        except Exception as e:
            self.log(f"Status check error: {e}")
            
    def authenticate(self):
        """Authenticate with session key"""
        session_key = self.key_entry.get().strip()
        if not session_key:
            self.log("Please enter a session key")
            return
            
        self.auth_btn.configure(state="disabled", text="Authenticating...")
        self.log("Starting authentication...")
        
        # Run in thread
        thread = threading.Thread(target=self._do_auth, args=(session_key,), daemon=True)
        thread.start()
        
    def _do_auth(self, session_key):
        """Perform authentication in background"""
        try:
            success, message, data = self.auth_handler.authenticate(session_key)
            
            # Update UI in main thread
            self.root.after(0, lambda: self.log(f"Result: {message}"))
            if success:
                self.root.after(0, lambda: self.status_label.configure(text="✓ Authenticated", text_color="green"))
                if data.get("organizations"):
                    for org in data["organizations"]:
                        self.root.after(0, lambda o=org: self.log(f"  - {o['name']}"))
            else:
                self.root.after(0, lambda: self.status_label.configure(text="✗ Failed", text_color="red"))
                
            self.root.after(0, lambda: self.auth_btn.configure(state="normal", text="Authenticate"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Error: {e}"))
            self.root.after(0, lambda: self.auth_btn.configure(state="normal", text="Authenticate"))
            
    def logout(self):
        """Logout"""
        self.logout_btn.configure(state="disabled")
        self.log("Logging out...")
        
        thread = threading.Thread(target=self._do_logout, daemon=True)
        thread.start()
        
    def _do_logout(self):
        """Perform logout in background"""
        try:
            success, message = self.auth_handler.logout()
            self.root.after(0, lambda: self.log(f"Logout: {message}"))
            self.root.after(0, self.check_status)
            self.root.after(0, lambda: self.logout_btn.configure(state="normal"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Logout error: {e}"))
            self.root.after(0, lambda: self.logout_btn.configure(state="normal"))
            
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = SimpleAuthTest()
    app.run()
