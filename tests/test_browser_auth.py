#!/usr/bin/env python
"""Test browser authentication for ClaudeSync."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from claudesync.browser_auth import BrowserAuth
import click


def test_playwright():
    """Test Playwright browser automation."""
    click.echo("Testing Playwright browser automation...")
    try:
        session_key = BrowserAuth.get_session_key_playwright(headless=False)
        if session_key:
            click.echo(f"✓ Success! Got session key: {session_key[:20]}...")
        else:
            click.echo("✗ Failed to get session key")
    except Exception as e:
        click.echo(f"✗ Error: {e}")


def test_selenium():
    """Test Selenium browser automation."""
    click.echo("Testing Selenium browser automation...")
    try:
        session_key = BrowserAuth.get_session_key_selenium()
        if session_key:
            click.echo(f"✓ Success! Got session key: {session_key[:20]}...")
        else:
            click.echo("✗ Failed to get session key")
    except Exception as e:
        click.echo(f"✗ Error: {e}")


if __name__ == "__main__":
    click.echo("ClaudeSync Browser Authentication Test")
    click.echo("=" * 40)
    
    choice = click.prompt(
        "\nWhich browser automation to test?",
        type=click.Choice(['playwright', 'selenium', 'both']),
        default='playwright'
    )
    
    if choice in ['playwright', 'both']:
        test_playwright()
    
    if choice in ['selenium', 'both']:
        test_selenium()
    
    click.echo("\nTest complete!")
