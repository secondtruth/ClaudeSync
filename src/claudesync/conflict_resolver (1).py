"""
Conflict resolution for ClaudeSync.
Handles cases where files are modified both locally and remotely.
"""

import os
import difflib
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """Available conflict resolution strategies."""
    KEEP_LOCAL = "local"
    KEEP_REMOTE = "remote" 
    MERGE_MANUAL = "manual"
    MERGE_AUTO = "auto"
    SKIP = "skip"


class ConflictInfo:
    """Information about a file conflict."""
    
    def __init__(self, file_path: str, local_content: str, remote_content: str):
        self.file_path = file_path
        self.local_content = local_content
        self.remote_content = remote_content
        self.resolution = None
        self.merged_content = None
    
    def get_diff(self) -> List[str]:
        """Get a unified diff between local and remote content."""
        local_lines = self.local_content.splitlines(keepends=True)
        remote_lines = self.remote_content.splitlines(keepends=True)
        
        return list(difflib.unified_diff(
            local_lines,
            remote_lines,
            fromfile=f"{self.file_path} (local)",
            tofile=f"{self.file_path} (remote)",
            lineterm=""
        ))
    
    def get_side_by_side_diff(self) -> List[str]:
        """Get a side-by-side diff for better visualization."""
        local_lines = self.local_content.splitlines()
        remote_lines = self.remote_content.splitlines()
        
        diff = []
        max_lines = max(len(local_lines), len(remote_lines))
        
        for i in range(max_lines):
            local_line = local_lines[i] if i < len(local_lines) else ""
            remote_line = remote_lines[i] if i < len(remote_lines) else ""
            
            # Simple change detection
            if local_line == remote_line:
                status = "  "  # Unchanged
            elif not local_line:
                status = "+ "  # Added in remote
            elif not remote_line:
                status = "- "  # Removed in remote
            else:
                status = "? "  # Changed
            
            diff.append(f"{status} {local_line:<50} | {remote_line}")
        
        return diff


class ConflictResolver:
    """Handles conflict resolution for file synchronization."""
    
    def __init__(self, config=None):
        self.config = config
        self.conflicts = []
        
    def detect_conflicts(self, local_files: Dict[str, str], remote_files: List[Dict]) -> List[ConflictInfo]:
        """
        Detect conflicts between local and remote files.
        
        Args:
            local_files: Dictionary of local file paths to checksums
            remote_files: List of remote file dictionaries
            
        Returns:
            List of ConflictInfo objects for conflicted files
        """
        conflicts = []
        
        # Create lookup for remote files
        remote_lookup = {rf['file_name']: rf for rf in remote_files}
        
        for local_path, local_checksum in local_files.items():
            if local_path in remote_lookup:
                remote_file = remote_lookup[local_path]
                remote_content = remote_file['content']
                
                # Calculate remote checksum
                from ..utils import compute_md5_hash
                remote_checksum = compute_md5_hash(remote_content)
                
                if local_checksum != remote_checksum:
                    # We have a conflict - read local content
                    local_file_path = os.path.join(self.config.get_local_path(), local_path)
                    try:
                        with open(local_file_path, 'r', encoding='utf-8') as f:
                            local_content = f.read()
                        
                        conflict = ConflictInfo(local_path, local_content, remote_content)
                        conflicts.append(conflict)
                        logger.info(f"Detected conflict in: {local_path}")
                        
                    except Exception as e:
                        logger.error(f"Error reading local file {local_path}: {e}")
        
        self.conflicts = conflicts
        return conflicts
    
    def resolve_conflict_interactive(self, conflict: ConflictInfo) -> ConflictResolution:
        """
        Resolve a conflict interactively with user input.
        
        Args:
            conflict: The ConflictInfo object to resolve
            
        Returns:
            The chosen resolution strategy
        """
        import click
        
        click.echo("\n" + "="*80)
        click.echo(f"🚨 CONFLICT DETECTED: {conflict.file_path}")
        click.echo("="*80)
        
        # Show file info
        local_size = len(conflict.local_content)
        remote_size = len(conflict.remote_content)
        click.echo(f"📁 Local version:  {local_size} characters")
        click.echo(f"☁️  Remote version: {remote_size} characters")
        click.echo("")
        
        # Show diff
        click.echo("📋 Differences (unified diff):")
        click.echo("-" * 40)
        
        diff_lines = conflict.get_diff()
        if diff_lines:
            for line in diff_lines[:20]:  # Show first 20 lines of diff
                if line.startswith('+'):
                    click.echo(click.style(line, fg='green'))
                elif line.startswith('-'):
                    click.echo(click.style(line, fg='red'))
                elif line.startswith('@@'):
                    click.echo(click.style(line, fg='cyan'))
                else:
                    click.echo(line)
            
            if len(diff_lines) > 20:
                click.echo(f"... ({len(diff_lines) - 20} more lines)")
        else:
            click.echo("No differences detected (encoding issue?)")
        
        click.echo("")
        
        # Present options
        click.echo("🔧 Resolution options:")
        click.echo("  1. Keep LOCAL version (overwrite remote)")
        click.echo("  2. Keep REMOTE version (overwrite local)")
        click.echo("  3. Open external editor for manual merge")
        click.echo("  4. Show side-by-side comparison")
        click.echo("  5. Skip this file (leave both versions as-is)")
        click.echo("")
        
        while True:
            choice = click.prompt("Choose resolution", type=click.Choice(['1', '2', '3', '4', '5']))
            
            if choice == '1':
                return ConflictResolution.KEEP_LOCAL
            elif choice == '2':
                return ConflictResolution.KEEP_REMOTE
            elif choice == '3':
                return self._manual_merge(conflict)
            elif choice == '4':
                self._show_side_by_side(conflict)
                continue  # Show menu again
            elif choice == '5':
                return ConflictResolution.SKIP
    
    def _show_side_by_side(self, conflict: ConflictInfo):
        """Show side-by-side comparison of the conflict."""
        import click
        
        click.echo("\n📊 Side-by-side comparison:")
        click.echo("="*100)
        click.echo(f"{'LOCAL' + ' '*46} | REMOTE")
        click.echo("-"*100)
        
        side_by_side = conflict.get_side_by_side_diff()
        for line in side_by_side[:30]:  # Show first 30 lines
            if line.startswith('+ '):
                click.echo(click.style(line, fg='green'))
            elif line.startswith('- '):
                click.echo(click.style(line, fg='red'))
            elif line.startswith('? '):
                click.echo(click.style(line, fg='yellow'))
            else:
                click.echo(line)
        
        if len(side_by_side) > 30:
            click.echo(f"... ({len(side_by_side) - 30} more lines)")
        
        click.echo("")
    
    def _manual_merge(self, conflict: ConflictInfo) -> ConflictResolution:
        """Open external editor for manual merge."""
        import click
        
        try:
            # Create temporary files for merge
            with tempfile.NamedTemporaryFile(mode='w', suffix='.local.md', delete=False) as local_tmp:
                local_tmp.write(conflict.local_content)
                local_tmp_path = local_tmp.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.remote.md', delete=False) as remote_tmp:
                remote_tmp.write(conflict.remote_content)
                remote_tmp_path = remote_tmp.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.merged.md', delete=False) as merged_tmp:
                merged_tmp.write(conflict.local_content)  # Start with local content
                merged_tmp_path = merged_tmp.name
            
            click.echo(f"📝 Opening external editor for manual merge...")
            click.echo(f"   Local version:  {local_tmp_path}")
            click.echo(f"   Remote version: {remote_tmp_path}")
            click.echo(f"   Merge into:     {merged_tmp_path}")
            click.echo("")
            click.echo("💡 Edit the merged file to resolve conflicts, then save and close.")
            
            # Try different editors
            editors = ['code', 'subl', 'atom', 'nano', 'vim', 'notepad']
            editor_launched = False
            
            for editor in editors:
                try:
                    subprocess.run([editor, merged_tmp_path], check=True)
                    editor_launched = True
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            if not editor_launched:
                click.echo("⚠️ Could not launch external editor. Manual merge not available.")
                return ConflictResolution.SKIP
            
            # Read the merged result
            with open(merged_tmp_path, 'r', encoding='utf-8') as f:
                conflict.merged_content = f.read()
            
            # Cleanup
            os.unlink(local_tmp_path)
            os.unlink(remote_tmp_path)
            os.unlink(merged_tmp_path)
            
            return ConflictResolution.MERGE_MANUAL
            
        except Exception as e:
            logger.error(f"Error during manual merge: {e}")
            click.echo(f"❌ Manual merge failed: {e}")
            return ConflictResolution.SKIP
    
    def apply_resolution(self, conflict: ConflictInfo, resolution: ConflictResolution) -> bool:
        """
        Apply the chosen resolution to a conflict.
        
        Args:
            conflict: The ConflictInfo object
            resolution: The chosen resolution strategy
            
        Returns:
            True if resolution was applied successfully
        """
        try:
            local_file_path = os.path.join(self.config.get_local_path(), conflict.file_path)
            
            if resolution == ConflictResolution.KEEP_LOCAL:
                # Local wins - no local file changes needed
                # Will be handled by sync process
                logger.info(f"Resolved {conflict.file_path}: keeping local version")
                return True
                
            elif resolution == ConflictResolution.KEEP_REMOTE:
                # Remote wins - overwrite local file
                with open(local_file_path, 'w', encoding='utf-8') as f:
                    f.write(conflict.remote_content)
                logger.info(f"Resolved {conflict.file_path}: keeping remote version")
                return True
                
            elif resolution == ConflictResolution.MERGE_MANUAL:
                # Use manually merged content
                if conflict.merged_content is not None:
                    with open(local_file_path, 'w', encoding='utf-8') as f:
                        f.write(conflict.merged_content)
                    logger.info(f"Resolved {conflict.file_path}: manual merge applied")
                    return True
                else:
                    logger.error(f"No merged content available for {conflict.file_path}")
                    return False
                    
            elif resolution == ConflictResolution.SKIP:
                # Do nothing - leave both versions as-is
                logger.info(f"Skipped conflict resolution for {conflict.file_path}")
                return True
                
            else:
                logger.error(f"Unknown resolution strategy: {resolution}")
                return False
                
        except Exception as e:
            logger.error(f"Error applying resolution for {conflict.file_path}: {e}")
            return False
    
    def resolve_all_conflicts(self, interactive: bool = True) -> Dict[str, ConflictResolution]:
        """
        Resolve all detected conflicts.
        
        Args:
            interactive: Whether to resolve conflicts interactively
            
        Returns:
            Dictionary mapping file paths to their resolution strategies
        """
        resolutions = {}
        
        if not self.conflicts:
            return resolutions
        
        import click
        click.echo(f"\n🚨 Found {len(self.conflicts)} file conflicts that need resolution")
        
        for i, conflict in enumerate(self.conflicts, 1):
            click.echo(f"\n📄 Resolving conflict {i}/{len(self.conflicts)}")
            
            if interactive:
                resolution = self.resolve_conflict_interactive(conflict)
            else:
                # Auto-resolve strategy (could be configurable)
                resolution = ConflictResolution.KEEP_LOCAL
                click.echo(f"Auto-resolving {conflict.file_path}: keeping local version")
            
            if self.apply_resolution(conflict, resolution):
                resolutions[conflict.file_path] = resolution
                conflict.resolution = resolution
            else:
                click.echo(f"❌ Failed to resolve conflict for {conflict.file_path}")
        
        return resolutions
