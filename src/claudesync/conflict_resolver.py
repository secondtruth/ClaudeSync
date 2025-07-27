import os
import difflib
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class ConflictResolver:
    """Handles file conflicts during synchronization."""
    
    def __init__(self, config):
        self.config = config
        self.conflicts = []
        
    def detect_conflicts(self, local_files: Dict[str, str], 
                        remote_files: List[Dict]) -> List[Dict]:
        """Detect conflicts between local and remote files."""
        conflicts = []
        
        for remote_file in remote_files:
            file_name = remote_file['file_name']
            if file_name in local_files:
                local_path = os.path.join(self.config.get('local_path'), file_name)
                
                # Read local content
                try:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        local_content = f.read()
                except Exception as e:
                    logger.error(f"Error reading local file {file_name}: {e}")
                    continue
                
                # Compare with remote
                remote_content = remote_file.get('content', '')
                
                # Check if files differ
                if self._normalize_content(local_content) != self._normalize_content(remote_content):
                    conflicts.append({
                        'file_name': file_name,
                        'local_path': local_path,
                        'local_content': local_content,
                        'remote_content': remote_content,
                        'local_modified': datetime.fromtimestamp(os.path.getmtime(local_path)),
                        'remote_modified': datetime.fromisoformat(remote_file['created_at'].replace('Z', '+00:00'))
                    })
        
        self.conflicts = conflicts
        return conflicts
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for comparison."""
        return content.replace('\r\n', '\n').replace('\r', '\n').strip()
    
    def resolve_conflict(self, conflict: Dict, strategy: str = 'prompt') -> str:
        """Resolve a single conflict based on strategy."""
        if strategy == 'local-wins':
            return conflict['local_content']
        elif strategy == 'remote-wins':
            return conflict['remote_content']
        elif strategy == 'prompt':
            return self._interactive_resolve(conflict)
        else:
            raise ValueError(f"Unknown resolution strategy: {strategy}")
    
    def _interactive_resolve(self, conflict: Dict) -> str:
        """Interactive conflict resolution."""
        import click
        
        file_name = conflict['file_name']
        click.echo(f"\nConflict detected in: {file_name}")
        click.echo(f"Local modified: {conflict['local_modified']}")
        click.echo(f"Remote modified: {conflict['remote_modified']}")
        
        choices = [
            ('l', 'Keep local version'),
            ('r', 'Keep remote version'),
            ('d', 'Show diff'),
            ('e', 'Edit in external editor'),
            ('s', 'Skip this file')
        ]
        
        while True:
            click.echo("\nOptions:")
            for key, desc in choices:
                click.echo(f"  [{key}] {desc}")
            
            choice = click.prompt("Choose an option", type=str).lower()
            
            if choice == 'l':
                return conflict['local_content']
            elif choice == 'r':
                return conflict['remote_content']
            elif choice == 'd':
                self._show_diff(conflict)
            elif choice == 'e':
                return self._edit_in_external_editor(conflict)
            elif choice == 's':
                return None
    
    def _show_diff(self, conflict: Dict):
        """Display diff between local and remote versions."""
        import click
        
        diff = difflib.unified_diff(
            conflict['remote_content'].splitlines(keepends=True),
            conflict['local_content'].splitlines(keepends=True),
            fromfile=f"{conflict['file_name']} (remote)",
            tofile=f"{conflict['file_name']} (local)"
        )
        
        click.echo_via_pager(''.join(diff))
    
    def _edit_in_external_editor(self, conflict: Dict) -> str:
        """Open conflict in external editor for resolution."""
        import click
        
        # Create temporary file with conflict markers
        with tempfile.NamedTemporaryFile(mode='w', suffix=f"_{conflict['file_name']}", 
                                       delete=False) as tmp:
            tmp.write(f"<<<<<<< LOCAL (modified: {conflict['local_modified']})\n")
            tmp.write(conflict['local_content'])
            tmp.write("\n=======\n")
            tmp.write(conflict['remote_content'])
            tmp.write(f"\n>>>>>>> REMOTE (modified: {conflict['remote_modified']})\n")
            tmp_path = tmp.name
        
        # Open in editor
        editor = os.environ.get('EDITOR', 'nano')
        subprocess.call([editor, tmp_path])
        
        # Read resolved content
        try:
            with open(tmp_path, 'r', encoding='utf-8') as f:
                resolved_content = f.read()
        finally:
            os.unlink(tmp_path)
        
        return resolved_content
    
    def get_conflict_summary(self) -> Dict:
        """Get summary of current conflicts."""
        return {
            'total_conflicts': len(self.conflicts),
            'files': [c['file_name'] for c in self.conflicts],
            'resolution_needed': len(self.conflicts) > 0
        }