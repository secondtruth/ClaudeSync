# ClaudeSync v0.7.5 - Simplified Authentication

## Overview
Version 0.7.5 introduces a much simpler authentication method that doesn't require browser automation libraries like Playwright or Selenium.

## New Features

### 1. Quick Authentication Command
```bash
csync auth quick
```

This new command provides two simple methods to get your session key:

#### Method A: Bookmarklet (Recommended)
1. Opens a helper page in your browser
2. Drag the bookmarklet button to your bookmarks bar
3. Go to claude.ai and log in
4. Click the bookmarklet - it copies your session key
5. Paste the key back in the terminal

#### Method B: Browser Console
1. Go to claude.ai and log in
2. Open DevTools (F12)
3. Paste the provided script in the console
4. Key is automatically copied to clipboard
5. Paste the key back in the terminal

### 2. Lightweight Implementation
- **No heavy dependencies**: No Playwright or Selenium required
- **Pure JavaScript**: Uses browser's native capabilities
- **Instant extraction**: Gets session key directly from cookies/storage
- **Clipboard integration**: Automatically copies key for easy pasting

### 3. Security Features
- Session keys are validated before storage
- Keys are hidden when typing (password input)
- Clear security warnings about not sharing keys
- Temporary HTML files are auto-cleaned after 60 seconds

## Comparison with Previous Methods

| Feature | Old Browser Auth | New Quick Auth |
|---------|-----------------|----------------|
| Dependencies | Playwright/Selenium | None (pyperclip optional) |
| Setup complexity | High | Low |
| Speed | Slow (browser launch) | Instant |
| User interaction | Automated | Manual (but simpler) |
| Reliability | Can fail with updates | Always works |

## Installation

```bash
# Navigate to ClaudeSync directory
cd /mnt/c/Users/jordans/Documents/GitHub/ClaudeSync

# Install with updated dependencies
pip install -e .

# Or just install pyperclip if upgrading
pip install pyperclip
```

## Usage Examples

### Quick Auth (New - Recommended)
```bash
# Interactive quick authentication
csync auth quick

# Follow the prompts to get your session key
```

### Traditional Methods (Still Available)
```bash
# Manual entry
csync auth login

# Direct session key
csync auth login --session-key sk-ant-YOUR-KEY-HERE

# Browser automation (requires browser extras)
csync auth browser-login
```

## How It Works

The bookmarklet/console script:
1. Checks document.cookie for session keys
2. Checks localStorage for session data
3. Checks sessionStorage as fallback
4. Validates the key format (sk-*)
5. Copies to clipboard
6. Shows visual confirmation

## Advantages
- **No browser automation**: More reliable, no version conflicts
- **User control**: User sees exactly what's happening
- **Faster**: No need to launch/control browser
- **Portable**: Bookmarklet works on any browser
- **Educational**: Users understand the auth process

## Testing

```bash
# Run the test suite
python tests/test_simple_auth.py

# Test the actual auth flow
csync auth quick
```

## Migration from v0.7.4
If you were using browser-login, switch to the new quick auth:
- Faster and more reliable
- No browser driver installation needed
- Works on all platforms consistently

## Next Steps
After authentication:
```bash
# Set organization
csync organization set

# Pull all project instructions
csync workspace sync-all --pull

# Start working
csync push
```
