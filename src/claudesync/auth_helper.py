"""
Simplified authentication helper for ClaudeSync.
No browser automation required - uses bookmarklet or console approach.
"""

import click
import webbrowser
import time
from pathlib import Path
import tempfile

# Optional import for clipboard support
try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False


class SimpleAuthHelper:
    """Simplified authentication using bookmarklet or console methods."""
    
    BOOKMARKLET = """javascript:(function(){const findSessionKey=()=>{const cookies=document.cookie.split(';').map(c=>c.trim());for(const cookie of cookies){if(cookie.includes('sessionKey=')||cookie.startsWith('sk-')){return cookie.split('=')[1];}}const storage=['localStorage','sessionStorage'];for(const store of storage){try{const keys=Object.keys(window[store]);for(const key of keys){const value=window[store].getItem(key);if(value&&value.startsWith('sk-')&&value.length>40){return value;}}}catch(e){}}return null;};const key=findSessionKey();if(key){navigator.clipboard.writeText(key).then(()=>{const notification=document.createElement('div');notification.style.cssText='position:fixed;top:20px;right:20px;background:#28a745;color:white;padding:15px 25px;border-radius:8px;z-index:10000;font-family:sans-serif;box-shadow:0 4px 12px rgba(0,0,0,0.3);animation:slideIn 0.3s ease;';notification.textContent='✅ Session key copied to clipboard!';const style=document.createElement('style');style.textContent='@keyframes slideIn{from{transform:translateX(400px);opacity:0;}to{transform:translateX(0);opacity:1;}}';document.head.appendChild(style);document.body.appendChild(notification);setTimeout(()=>{notification.style.animation='slideIn 0.3s ease reverse';setTimeout(()=>{document.body.removeChild(notification);document.head.removeChild(style);},300);},3000);}).catch(err=>{alert('Session key found but clipboard access failed. Key: '+key.substring(0,20)+'...');});}else{alert('No session key found. Make sure you are logged into Claude.ai');}})();"""
    
    CONSOLE_SCRIPT = """
// Paste this in the browser console (F12) while on claude.ai:
(function() {
    const findSessionKey = () => {
        // Check cookies
        const cookies = document.cookie.split(';').map(c => c.trim());
        for (const cookie of cookies) {
            if (cookie.includes('sessionKey=') || cookie.startsWith('sk-')) {
                return cookie.split('=')[1];
            }
        }
        
        // Check localStorage and sessionStorage  
        const storage = ['localStorage', 'sessionStorage'];
        for (const store of storage) {
            try {
                const keys = Object.keys(window[store]);
                for (const key of keys) {
                    const value = window[store].getItem(key);
                    if (value && value.startsWith('sk-') && value.length > 40) {
                        return value;
                    }
                }
            } catch(e) {}
        }
        
        return null;
    };
    
    const key = findSessionKey();
    if (key) {
        console.log('Session key found!');
        console.log('Key:', key);
        copy(key); // Chrome DevTools copy function
        console.log('✅ Key copied to clipboard!');
    } else {
        console.log('❌ No session key found');
    }
})();
"""

    @classmethod
    def quick_auth(cls) -> str:
        """Interactive quick authentication flow."""
        click.echo("\n🔑 ClaudeSync Quick Authentication")
        click.echo("=" * 40)
        
        # Option 1: Open helper page
        if click.confirm("\nWould you like to open the auth helper page?"):
            cls._open_helper_page()
            click.echo("\n✓ Helper page opened in your browser")
            click.echo("Follow the instructions to get your session key")
            
        # Option 2: Show console script
        else:
            click.echo("\n📋 Manual Method:")
            click.echo("1. Go to https://claude.ai and log in")
            click.echo("2. Open DevTools (F12)")
            click.echo("3. Go to Console tab")
            click.echo("4. Paste this code:\n")
            click.echo(click.style(cls.CONSOLE_SCRIPT, fg='cyan'))
            
            # Copy to clipboard if available
            if HAS_CLIPBOARD:
                try:
                    pyperclip.copy(cls.CONSOLE_SCRIPT)
                    click.echo("\n✓ Script copied to clipboard!")
                except:
                    pass
        
        # Wait for user to get key
        click.echo("\n" + "=" * 40)
        session_key = click.prompt("\nPaste your session key here", hide_input=True)
        
        if session_key and session_key.startswith('sk-'):
            click.echo(click.style("✓ Valid session key format", fg='green'))
            return session_key
        else:
            click.echo(click.style("✗ Invalid key format", fg='red'))
            return None
    
    @classmethod  
    def _open_helper_page(cls):
        """Create and open the helper HTML page."""
        html_content = cls._get_helper_html()
        
        # Create temp HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_path = f.name
        
        # Open in browser
        webbrowser.open(f'file://{temp_path}')
        
        # Clean up after a delay
        def cleanup():
            time.sleep(60)
            try:
                Path(temp_path).unlink()
            except:
                pass
        
        import threading
        threading.Thread(target=cleanup, daemon=True).start()
    
    @classmethod
    def _get_helper_html(cls) -> str:
        """Get the helper HTML page content."""
        return f'''<!DOCTYPE html>
<html>
<head>
    <title>ClaudeSync Auth Helper</title>
    <style>
        body {{
            font-family: -apple-system, system-ui, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .bookmarklet {{
            display: inline-block;
            background: #5e72e4;
            color: white;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            margin: 20px 0;
        }}
        .bookmarklet:hover {{
            background: #4c63d2;
        }}
        .step {{
            margin: 15px 0;
            padding-left: 25px;
        }}
        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔑 ClaudeSync Auth Helper</h1>
        
        <p>Drag this button to your bookmarks bar:</p>
        
        <a href="{cls.BOOKMARKLET}" class="bookmarklet">
            Get Claude Session Key
        </a>
        
        <h3>Instructions:</h3>
        <ol class="step">
            <li>Drag the button above to your bookmarks bar</li>
            <li>Go to <a href="https://claude.ai">claude.ai</a> and log in</li>
            <li>Click the bookmarklet</li>
            <li>Your session key will be copied to clipboard</li>
            <li>Return to terminal and paste the key</li>
        </ol>
        
        <p style="margin-top: 30px; padding: 15px; background: #fff3cd; border-radius: 6px;">
            <strong>Security:</strong> Never share your session key with anyone.
        </p>
    </div>
</body>
</html>'''
    
    @classmethod
    def validate_session_key(cls, key: str) -> bool:
        """Basic validation of session key format."""
        if not key:
            return False
        
        # Check if it looks like a session key
        if not key.startswith('sk-'):
            return False
        
        # Check minimum length
        if len(key) < 40:
            return False
        
        return True
