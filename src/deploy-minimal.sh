#!/bin/bash
# Deploy minimal ClaudeSync with workspace-wide sync

echo "🚀 Deploying Minimal ClaudeSync..."

# Step 1: Save these files to your repo
echo "Step 1: Save the new files"
echo "  • Save workspace_sync.py to src/claudesync/workspace_sync.py"
echo "  • Save the new main.py to src/claudesync/cli/main_minimal.py"

# Step 2: Backup original main.py
echo -e "\nStep 2: Backup original CLI"
if [ -f "src/claudesync/cli/main.py" ]; then
    cp src/claudesync/cli/main.py src/claudesync/cli/main_original.py
    echo "  ✅ Backed up original main.py"
fi

# Step 3: Switch to minimal CLI
echo -e "\nStep 3: Activate minimal CLI"
echo "Run: cp src/claudesync/cli/main_minimal.py src/claudesync/cli/main.py"

# Step 4: Update pyproject.toml (optional - keep both commands)
echo -e "\nStep 4: Update entry points in pyproject.toml:"
cat << 'EOF'
[project.scripts]
claudesync = "claudesync.cli.main:cli"  # Keep for compatibility
csync = "claudesync.cli.main:cli"       # Short version

# Or add a new command for workspace sync:
wsync = "claudesync.cli.main:cli"       # Workspace sync specific
EOF

# Step 5: Reinstall
echo -e "\nStep 5: Reinstall package"
echo "Run: pip install -e ."

# Step 6: Test
echo -e "\nStep 6: Test commands"
cat << 'EOF'
# Test authentication
csync auth status

# Initialize workspace
csync workspace init ~/ClaudeProjects

# Dry run sync
csync workspace sync --dry-run

# Real sync
csync workspace sync

# Check status
csync workspace status --detailed
EOF

echo -e "\n✨ Done! Your minimal ClaudeSync is ready."
echo "Only 4 commands: auth (login/logout/status), workspace (init/sync/status)"