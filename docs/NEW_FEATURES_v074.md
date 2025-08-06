# ClaudeSync v0.7.4 - New Features

## 1. Pull Support in Workspace Sync

The `csync workspace sync-all` command now supports pulling remote files before pushing local changes. This ensures you get all remote files (including `project-instructions.md`) that may not exist locally.

### Usage

```bash
# Pull remote files first, then push local changes
csync workspace sync-all --pull

# Preview what would happen (dry run)
csync workspace sync-all --pull --dry-run

# Sequential sync with pull (one project at a time)
csync workspace sync-all --pull --sequential
```

### Benefits
- Ensures you have all remote project files locally
- Prevents accidental overwrites
- Properly syncs `project-instructions.md` files from Claude.ai

## 2. Browser Authentication

Automatically retrieve session keys from your browser - no more manual copying!

### Installation

```bash
# Install ClaudeSync with browser support
pip install claudesync[browser]

# For Playwright (recommended)
playwright install chromium

# For Selenium (alternative)
# Download ChromeDriver from https://chromedriver.chromium.org/
```

### Usage

```bash
# Use Playwright to grab session key (recommended)
csync auth browser-login

# Use Selenium/Chrome
csync auth browser-login --browser selenium

# Run in headless mode (Playwright only)
csync auth browser-login --headless
```

### How It Works

1. Opens a browser window to Claude.ai
2. If you're already logged in, automatically grabs the session key
3. If not logged in, waits for you to log in (up to 2 minutes)
4. Automatically extracts and saves the session key
5. Verifies access to your organizations

### Troubleshooting

If browser authentication fails:
- Ensure you have a Claude Pro or Team subscription
- Check your internet connection
- For Selenium: Ensure ChromeDriver is installed and in PATH
- For Playwright: Run `playwright install chromium` if not installed
- Try running without `--headless` if authentication fails

## Migration Notes

For existing users:
1. Update ClaudeSync: `pip install --upgrade claudesync[browser]`
2. Reinstall to activate new commands: `pip install -e .` (from repo directory)
3. Use `--pull` flag with sync-all to ensure you get all remote files

## Examples

### Complete Workflow

```bash
# Authenticate with browser
csync auth browser-login

# Set organization
csync organization set

# Clone all projects
csync workspace clone

# Sync all projects (pull then push)
csync workspace sync-all --pull

# Check project instructions status
cd "your-project"
csync project instructions status
```

### Fix Missing project-instructions.md

If your projects are missing `project-instructions.md`:

```bash
# Pull all remote files for all projects
csync workspace sync-all --pull

# Or for a single project
cd "your-project"
csync pull
```
