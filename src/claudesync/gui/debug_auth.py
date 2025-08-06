"""
Debug script to test authentication directly
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from claudesync.gui.auth_handler import AuthHandler
    from claudesync.providers.claude_ai import ClaudeAIProvider
    
    print("Testing ClaudeSync Authentication Debug Tool")
    print("=" * 50)
    
    # Test 1: Import check
    print("✓ Successfully imported required modules")
    
    # Test 2: Create auth handler
    auth = AuthHandler()
    print("✓ Created AuthHandler instance")
    
    # Test 3: Check current status
    status = auth.get_current_auth_status()
    print(f"\nCurrent auth status: {'Authenticated' if status.get('authenticated') else 'Not authenticated'}")
    
    if status.get('authenticated'):
        print(f"Organizations found: {len(status.get('organizations', []))}")
        if status.get('active_organization'):
            print(f"Active org: {status['active_organization']['name']}")
    
    # Test 4: Test authentication flow (if not authenticated)
    if not status.get('authenticated'):
        print("\nTo test authentication:")
        print("1. Get your session key from Claude.ai")
        print("2. Run: python debug_auth.py YOUR_SESSION_KEY")
        
        if len(sys.argv) > 1:
            session_key = sys.argv[1]
            print(f"\nTesting authentication with provided key...")
            success, message, data = auth.authenticate(session_key)
            print(f"Result: {'Success' if success else 'Failed'}")
            print(f"Message: {message}")
            if data.get('organizations'):
                print(f"Organizations: {[org['name'] for org in data['organizations']]}")
    
except Exception as e:
    print(f"Error during testing: {e}")
    import traceback
    traceback.print_exc()
