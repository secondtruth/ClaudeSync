"""
Direct authentication handler for GUI - bypasses CLI complexity
"""
import json
import os
from pathlib import Path

try:
    from claudesync.providers.claude_ai import ClaudeAIProvider
    from claudesync.configmanager.file_config_manager import FileConfigManager
    from claudesync.exceptions import ProviderError
except ImportError as e:
    print(f"Import error: {e}")
    print("Trying alternative import path...")
    import sys
    # Add parent directories to path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir.parent.parent))
    sys.path.insert(0, str(current_dir.parent.parent.parent))
    
    from providers.claude_ai import ClaudeAIProvider
    from configmanager.file_config_manager import FileConfigManager
    from exceptions import ProviderError


class AuthHandler:
    """Handle authentication directly without subprocess calls"""
    
    def __init__(self):
        self.config_manager = FileConfigManager()
    
    def authenticate(self, session_key: str) -> tuple[bool, str, dict]:
        """
        Authenticate with Claude.ai directly
        
        Returns:
            tuple: (success, message, organization_data)
        """
        try:
            # Create provider instance
            provider = ClaudeAIProvider(session_key)
            
            # Test authentication by getting organizations
            orgs = provider.get_organizations()
            
            if not orgs:
                return False, "No organizations found. Ensure you have a Pro/Team account.", {}
            
            # Store the session key
            self.config_manager.set_session_key("claude.ai", session_key)
            
            # Return success with org data
            return True, "Authentication successful!", {
                "organizations": orgs,
                "session_key": session_key
            }
            
        except ProviderError as e:
            return False, f"Authentication failed: {str(e)}", {}
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", {}
    
    def get_current_auth_status(self) -> dict:
        """Get current authentication status"""
        try:
            session_key = self.config_manager.get_session_key("claude.ai")
            if not session_key:
                return {"authenticated": False}
            
            provider = ClaudeAIProvider(session_key)
            orgs = provider.get_organizations()
            
            # Get active org
            active_org_id = self.config_manager.get("active_organization_id")
            active_org = None
            if active_org_id:
                active_org = next((o for o in orgs if o["id"] == active_org_id), None)
            
            return {
                "authenticated": True,
                "organizations": orgs,
                "active_organization": active_org
            }
        except:
            return {"authenticated": False}
    
    def set_organization(self, org_id: str, org_name: str) -> tuple[bool, str]:
        """Set active organization"""
        try:
            self.config_manager.set("active_organization_id", org_id, local=False)
            self.config_manager.set("active_organization_name", org_name, local=False)
            return True, f"Set active organization to: {org_name}"
        except Exception as e:
            return False, f"Failed to set organization: {str(e)}"
    
    def logout(self) -> tuple[bool, str]:
        """Clear authentication"""
        try:
            # Clear session key
            config_path = Path.home() / ".claudesync" / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                if "providers" in config and "claude.ai" in config["providers"]:
                    del config["providers"]["claude.ai"]
                
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            
            # Clear organization settings
            self.config_manager.set("active_organization_id", None, local=False)
            self.config_manager.set("active_organization_name", None, local=False)
            
            return True, "Logged out successfully"
        except Exception as e:
            return False, f"Logout failed: {str(e)}"
