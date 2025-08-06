# ClaudeSync GUI Authentication Troubleshooting

## Changes Made

I've completely rewritten the authentication to bypass subprocess calls and use the ClaudeSync API directly. This should fix the hanging issue.

### Key Changes:

1. **New `auth_handler.py`** - Direct API authentication without subprocess
2. **Updated `main.py`** - Uses auth_handler instead of run_csync_command for auth
3. **Thread-safe implementation** - All auth operations run in background threads
4. **Better error handling** - More detailed error messages

## Testing Tools

### 1. Debug Script
```bash
cd src/claudesync/gui
python debug_auth.py [YOUR_SESSION_KEY]
```

### 2. Test GUI
```bash
cd src/claudesync/gui
python test_auth_gui.py
# Or double-click test_auth.bat
```

### 3. Main GUI
```bash
python -m claudesync.gui.main
# Or use ClaudeSync_GUI.bat
```

## Common Issues & Solutions

### Session Key Issues
- **Special characters**: The new implementation handles these properly
- **Whitespace**: Keys are automatically trimmed
- **Invalid format**: Will show clear error message

### If Authentication Still Hangs

1. **Check Python packages**:
   ```bash
   pip install --upgrade claudesync[gui]
   pip install --upgrade requests
   ```

2. **Check network**:
   - Ensure Claude.ai is accessible
   - Check proxy settings
   - Try in a browser first

3. **Debug mode**:
   ```python
   # In auth_handler.py, add after line 23:
   print(f"Attempting auth with key: {session_key[:10]}...")
   print(f"Provider created, getting orgs...")
   ```

4. **Alternative: Direct config edit**:
   If all else fails, you can manually add the session key:
   ```json
   # Edit ~/.claudesync/config.json
   {
     "providers": {
       "claude.ai": {
         "session_key": "YOUR_KEY_HERE"
       }
     }
   }
   ```

## What the New Implementation Does

1. **Direct API calls**: No subprocess, no command parsing
2. **Immediate feedback**: Shows exactly what's happening
3. **Proper threading**: GUI never freezes
4. **Better errors**: Specific messages about what went wrong

## Getting Your Session Key

1. Open Claude.ai in your browser
2. Open Developer Tools (F12)
3. Go to Application → Cookies → claude.ai
4. Find `sessionKey` cookie
5. Copy the entire value (it's long!)

## Next Steps

1. Try the test GUI first - it's simpler and shows detailed output
2. If that works, the main GUI should work too
3. If issues persist, check the debug output in the terminal

The authentication should now:
- ✓ Not freeze the GUI
- ✓ Show progress immediately
- ✓ Give clear error messages
- ✓ Work with all session key formats
