"""
Simple test to verify authentication works
"""
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

print("Testing ClaudeSync Authentication")
print("=" * 50)

# Test 1: Basic imports
try:
    import claudesync
    print("✓ ClaudeSync package found")
except ImportError as e:
    print(f"✗ ClaudeSync package not found: {e}")
    print("  Try: pip install claudesync")
    sys.exit(1)

# Test 2: Provider import
try:
    from claudesync.providers.claude_ai import ClaudeAIProvider
    print("✓ ClaudeAIProvider imported")
except ImportError as e:
    print(f"✗ Failed to import provider: {e}")
    sys.exit(1)

# Test 3: Config manager import
try:
    from claudesync.configmanager.file_config_manager import FileConfigManager
    print("✓ FileConfigManager imported")
except ImportError as e:
    print(f"✗ Failed to import config manager: {e}")
    sys.exit(1)

# Test 4: Check current config
try:
    config_path = Path.home() / ".claudesync" / "config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if "providers" in config and "claude.ai" in config["providers"]:
            print("✓ Existing Claude.ai configuration found")
        else:
            print("✗ No Claude.ai configuration found")
    else:
        print("✗ No config file found at:", config_path)
except Exception as e:
    print(f"✗ Error reading config: {e}")

# Test 5: Try auth handler
try:
    from auth_handler import AuthHandler
    auth = AuthHandler()
    print("✓ AuthHandler created")
    
    status = auth.get_current_auth_status()
    if status.get("authenticated"):
        print("✓ Currently authenticated")
        print(f"  Organizations: {len(status.get('organizations', []))}")
    else:
        print("✗ Not authenticated")
except Exception as e:
    print(f"✗ AuthHandler error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
