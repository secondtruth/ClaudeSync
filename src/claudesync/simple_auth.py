"""Simple authentication helper - no browser automation needed."""
import click
import json
import webbrowser
from typing import Optional

class SimpleAuth:
    """Simple session key extraction without browser automation."""
    
    @staticmethod
    def create_bookmarklet() -> str:
        """Create a bookmarklet to extract session key."""
        return """javascript:(function(){
            const cookies = document.cookie.split(';').map(c => c.trim());
            const sessionCookie = cookies.find(c => c.includes('sessionKey'));
            if(sessionCookie){
                const key = sessionCookie.split('=')[1];
                navigator.clipboard.writeText(key);
                alert('Session key copied to clipboard! Paste it in the terminal.');
            }else{
                alert('No session key found. Make sure you are logged in to Claude.ai');
            }
        })();"""
    
    @staticmethod
    def create_helper_script() -> str:
        """Create a helper script that can be pasted into browser console."""
        return """
// Claude Session Key Extractor
// Paste this into the browser console while on claude.ai

(function() {
    const cookies = document.cookie.split(';').map(c => c.trim());
    const sessionCookie = cookies.find(c => c.includes('sessionKey'));
    
    if(sessionCookie) {
        const key = sessionCookie.split('=')[1];
        console.log('\\n🔑 Found session key!');
        console.log('\\nYour session key is:');
        console.log(key);
        
        // Try to copy to clipboard
        if(navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(key).then(() => {
                console.log('\\n✅ Session key copied to clipboard!');
            }).catch(() => {
                console.log('\\n⚠️  Could not copy to clipboard. Please copy the key manually.');
            });
        }
    } else {
        console.log('❌ No session key found. Make sure you are:');
        console.log('1. On claude.ai (not a different domain)');
        console.log('2. Logged in to your account');
    }
})();
"""
    
    @staticmethod
    def get_session_key_simple() -> Optional[str]:
        """Guide user through simple session key extraction."""
        click.echo("\n🔐 Simple Session Key Extraction")
        click.echo("=" * 40)
        
        # Open Claude.ai
        click.echo("\n1. Opening Claude.ai in your browser...")
        webbrowser.open("https://claude.ai")
        
        click.echo("\n2. Make sure you are logged in to Claude.ai")
        click.echo("\n3. Choose one of these methods:\n")
        
        click.echo("   METHOD A - Browser Console (Recommended):")
        click.echo("   • Press F12 to open Developer Tools")
        click.echo("   • Click on the 'Console' tab")
        click.echo("   • Paste this command and press Enter:\n")
        
        console_cmd = "document.cookie.split(';').find(c=>c.includes('sessionKey')).split('=')[1]"
        click.echo(f"     {console_cmd}")
        
        click.echo("\n   METHOD B - Bookmarklet:")
        click.echo("   • Create a bookmark with this as the URL:")
        bookmarklet = SimpleAuth.create_bookmarklet()
        click.echo(f"\n     {bookmarklet[:80]}...")
        click.echo("     (Full bookmarklet saved to 'claude_auth_bookmarklet.txt')")
        
        # Save bookmarklet to file
        with open("claude_auth_bookmarklet.txt", "w") as f:
            f.write(bookmarklet)
        
        click.echo("\n   METHOD C - Helper Script:")
        click.echo("   • Run: csync auth show-helper")
        click.echo("   • Copy the script and paste in browser console")
        
        click.echo("\n4. Paste your session key below:")
        
        session_key = click.prompt("Session key (sk-ant-...)", hide_input=False).strip()
        
        if session_key.startswith("sk-ant-"):
            return session_key
        else:
            raise click.ClickException("Invalid session key format. Should start with 'sk-ant-'")
    
    @staticmethod
    def show_helper_script():
        """Display the helper script for manual extraction."""
        script = SimpleAuth.create_helper_script()
        
        click.echo("\n📋 Copy and paste this script into the browser console on claude.ai:\n")
        click.echo("-" * 60)
        click.echo(script)
        click.echo("-" * 60)
        
        # Also save to file
        with open("claude_session_extractor.js", "w") as f:
            f.write(script)
        
        click.echo("\n✅ Script also saved to: claude_session_extractor.js")
        click.echo("\nInstructions:")
        click.echo("1. Open claude.ai and log in")
        click.echo("2. Press F12 to open Developer Tools")
        click.echo("3. Click on the 'Console' tab")
        click.echo("4. Paste the script above and press Enter")
        click.echo("5. Copy the session key that appears")
