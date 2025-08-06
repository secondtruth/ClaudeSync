#!/usr/bin/env python3
"""
Test the simplified authentication helper.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from claudesync.auth_helper import SimpleAuthHelper

def test_validation():
    """Test session key validation."""
    print("Testing session key validation...")
    
    # Valid keys
    valid_keys = [
        "sk-ant-" + "a" * 50,
        "sk-ant-sid01-" + "x" * 80,
        "sk-" + "b" * 100
    ]
    
    # Invalid keys
    invalid_keys = [
        "",
        "invalid",
        "sk-",
        "sk-" + "a" * 10,  # Too short
        "not-a-key"
    ]
    
    for key in valid_keys:
        assert SimpleAuthHelper.validate_session_key(key), f"Should be valid: {key[:20]}..."
        
    for key in invalid_keys:
        assert not SimpleAuthHelper.validate_session_key(key), f"Should be invalid: {key}"
    
    print("✓ Validation tests passed")

def test_scripts():
    """Test that scripts are defined."""
    print("Testing script definitions...")
    
    assert len(SimpleAuthHelper.BOOKMARKLET) > 100, "Bookmarklet should be defined"
    assert len(SimpleAuthHelper.CONSOLE_SCRIPT) > 100, "Console script should be defined"
    assert "findSessionKey" in SimpleAuthHelper.BOOKMARKLET
    assert "findSessionKey" in SimpleAuthHelper.CONSOLE_SCRIPT
    
    print("✓ Script tests passed")

def test_html_generation():
    """Test HTML helper page generation."""
    print("Testing HTML generation...")
    
    html = SimpleAuthHelper._get_helper_html()
    assert "<html>" in html
    assert "ClaudeSync Auth Helper" in html
    assert SimpleAuthHelper.BOOKMARKLET in html
    
    print("✓ HTML generation passed")

if __name__ == "__main__":
    print("\n🧪 Testing Simplified Auth Helper\n")
    
    test_validation()
    test_scripts()  
    test_html_generation()
    
    print("\n✅ All tests passed!\n")
    print("You can now test the auth flow with:")
    print("  csync auth quick")
    print("\nOr use the bookmarklet/console method directly.")
