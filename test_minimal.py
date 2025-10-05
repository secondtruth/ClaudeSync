#!/usr/bin/env python3
"""
Test script to verify minimal ClaudeSync setup
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, '/mnt/c/Users/jordans/Documents/GitHub/ClaudeSync/src')

def test_imports():
    """Test all required imports work."""
    print("Testing imports...")
    
    try:
        from claudesync.configmanager import FileConfigManager
        print("✅ FileConfigManager imported")
    except ImportError as e:
        print(f"❌ FileConfigManager import failed: {e}")
        return False
    
    try:
        from claudesync.session_key_manager import SessionKeyManager
        print("✅ SessionKeyManager imported")
    except ImportError as e:
        print(f"❌ SessionKeyManager import failed: {e}")
        return False
    
    try:
        from claudesync.provider_factory import get_provider
        print("✅ provider_factory imported")
    except ImportError as e:
        print(f"❌ provider_factory import failed: {e}")
        return False
        
    try:
        from claudesync.workspace_sync import WorkspaceSync
        print("✅ WorkspaceSync imported")
    except ImportError as e:
        print(f"❌ WorkspaceSync import failed: {e}")
        return False
    
    return True

def test_auth_check():
    """Test auth status check."""
    print("\nTesting auth status...")
    
    try:
        from claudesync.session_key_manager import SessionKeyManager
        session_mgr = SessionKeyManager()
        session_key = session_mgr.get_session_key()
        
        if session_key:
            print(f"✅ Found session key (first 20 chars): {session_key[:20]}...")
        else:
            print("⚠️  No session key found (this is OK if not logged in)")
    except Exception as e:
        print(f"❌ Auth check failed: {e}")
        return False
    
    return True

def test_workspace_init():
    """Test workspace initialization."""
    print("\nTesting workspace initialization...")
    
    try:
        from claudesync.workspace_sync import WorkspaceSync
        from claudesync.provider_factory import get_provider
        
        # Mock provider for test
        provider = get_provider("claude.ai")
        
        # Test workspace path
        test_path = Path("/tmp/test_claude_workspace")
        
        # Create workspace sync instance
        ws = WorkspaceSync(test_path, provider)
        
        # Check if config was created
        config_path = Path.home() / ".claudesync" / "workspace.json"
        if config_path.exists():
            print(f"✅ Config file exists: {config_path}")
        else:
            print(f"⚠️  Config file not found (will be created on first sync)")
        
        # Check workspace directory
        if test_path.exists():
            print(f"✅ Workspace directory created: {test_path}")
        else:
            print(f"❌ Workspace directory not created")
            return False
            
    except Exception as e:
        print(f"❌ Workspace init failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    print("=" * 50)
    print("ClaudeSync Minimal Implementation Test")
    print("=" * 50)
    
    # Run tests
    success = True
    
    if not test_imports():
        success = False
    
    if not test_auth_check():
        success = False
        
    if not test_workspace_init():
        success = False
    
    # Summary
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed!")
        print("\nNext steps:")
        print("1. Run: python src/claudesync/cli/minimal-cli.py auth status")
        print("2. If not authenticated: python src/claudesync/cli/minimal-cli.py auth login")
        print("3. Initialize workspace: python src/claudesync/cli/minimal-cli.py workspace init ~/ClaudeProjects")
        print("4. Sync all projects: python src/claudesync/cli/minimal-cli.py workspace sync")
    else:
        print("❌ Some tests failed. Check errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
