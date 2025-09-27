"""
Workspace-wide sync for ALL Claude.ai projects at once.
Simple, centralized, efficient.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from tqdm import tqdm

from claudesync.exceptions import ProviderError
from claudesync.provider_factory import get_provider
from claudesync.utils import compute_md5_hash


def safe_print(text: str):
    """Safely print text with Unicode characters, handling console encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters with safe equivalents
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text)


class WorkspaceSync:
    """Sync ALL Claude.ai projects to local workspace folders."""
    
    def __init__(self, workspace_root: Path, provider):
        self.root = Path(workspace_root)
        self.provider = provider
        self.root.mkdir(parents=True, exist_ok=True)
        
        # Centralized config location
        self.config_dir = Path.home() / ".claudesync"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "workspace.json"
        
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load centralized workspace config."""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}

        # Ensure required keys exist
        config.setdefault("workspace_root", str(self.root))
        config.setdefault("project_map", {})
        config.setdefault("last_sync", None)

        return config
    
    def _save_config(self):
        """Save centralized config."""
        self.config["workspace_root"] = str(self.root)
        self.config["last_sync"] = datetime.now().isoformat()
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize project name for folder, preserving emojis."""
        # Keep alphanumeric, spaces, hyphens, underscores, and emojis
        sanitized = re.sub(r'[^\w\s\-_\u0080-\uFFFF]+', '', name)
        return sanitized.strip() or "unnamed_project"
    
    def sync_all(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Sync ALL projects from Claude.ai to local folders.
        Returns stats: {created: N, updated: N, skipped: N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
        
        try:
            # Get active organization
            orgs = self.provider.get_organizations()
            if not orgs:
                raise ProviderError("No organizations found")
            
            active_org = orgs[0]  # Use first org (we can enhance later)
            print(f"Using organization: {active_org['name']}")
            
            # Get all projects
            projects = self.provider.get_projects(
                active_org['id'],
                include_archived=False
            )
            
            if not projects:
                print("No projects found.")
                return stats
            
            print(f"Found {len(projects)} projects to sync\n")
            
            # Sync each project
            with tqdm(total=len(projects), desc="Syncing projects") as pbar:
                for project in projects:
                    result = self._sync_project(
                        active_org['id'],
                        project, 
                        dry_run
                    )
                    stats[result] += 1
                    pbar.update(1)
            
        except Exception as e:
            print(f"X Sync failed: {e}")
            stats["errors"] += 1
        
        # Save updated config
        if not dry_run:
            self._save_config()
        
        return stats
    
    def _sync_project(self, org_id: str, project: dict, dry_run: bool) -> str:
        """
        Sync individual project to folder.
        Returns: 'created', 'updated', 'skipped', or 'errors'
        """
        try:
            project_id = project['id']
            project_name = project['name']
            
            # Determine folder name
            if project_id in self.config["project_map"]:
                folder_name = self.config["project_map"][project_id]
            else:
                folder_name = self._sanitize_name(project_name)
                # Handle duplicates
                base_name = folder_name
                counter = 1
                while (self.root / folder_name).exists():
                    folder_name = f"{base_name}_{counter}"
                    counter += 1
                self.config["project_map"][project_id] = folder_name
            
            folder_path = self.root / folder_name
            
            # Dry run - just show what would happen
            if dry_run:
                if folder_path.exists():
                    safe_print(f"  Would update: {folder_name}")
                    return "updated"
                else:
                    safe_print(f"  Would create: {folder_name}")
                    return "created"
            
            # Create folder if needed
            is_new = not folder_path.exists()
            folder_path.mkdir(exist_ok=True)
            
            # Sync project instructions to AGENTS.md
            try:
                instructions_response = self.provider.get_project_instructions(org_id, project_id)
                if instructions_response and 'template' in instructions_response:
                    instructions = instructions_response['template']
                    if instructions and instructions.strip():
                        agents_path = folder_path / "AGENTS.md"

                        # Check if AGENTS.md needs updating
                        needs_update = True
                        if agents_path.exists():
                            with open(agents_path, 'r', encoding='utf-8') as f:
                                local_instructions = f.read()
                            needs_update = instructions.strip() != local_instructions.strip()

                        if needs_update and not dry_run:
                            with open(agents_path, 'w', encoding='utf-8') as f:
                                f.write(instructions)
            except Exception as e:
                safe_print(f"    Warning: Could not sync instructions: {e}")

            # Get remote files (exclude AGENTS.md to prevent duplication)
            remote_files = self.provider.list_files(org_id, project_id)
            remote_files = [f for f in remote_files if f['file_name'] != 'AGENTS.md']

            if not remote_files:
                return "skipped"

            # Download all files (AGENTS.md already handled above)
            for remote_file in remote_files:
                file_path = folder_path / remote_file['file_name']
                
                # Skip if local file matches remote
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        local_content = f.read()
                    local_hash = compute_md5_hash(local_content)

                    # Get remote content (already included in list_files response)
                    remote_content = remote_file['content']
                    remote_hash = compute_md5_hash(remote_content)
                    
                    if local_hash == remote_hash:
                        continue
                
                # Download file (content already available from list_files)
                content = remote_file['content']

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Create .claudesync marker
            marker = folder_path / ".claudesync"
            marker.mkdir(exist_ok=True)
            
            info_file = marker / "project.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "id": project_id,
                    "name": project_name,
                    "org_id": org_id,
                    "synced_at": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            
            return "created" if is_new else "updated"
            
        except Exception as e:
            safe_print(f"  X Error syncing {project['name']}: {e}")
            return "errors"
    
    def status(self) -> dict:
        """Show workspace sync status."""
        status = {
            "workspace_root": str(self.root),
            "total_projects": len(self.config.get("project_map", {})),
            "last_sync": self.config.get("last_sync"),
            "local_folders": 0,
            "orphaned_folders": []
        }
        
        # Check local folders
        if self.root.exists():
            for folder in self.root.iterdir():
                if folder.is_dir() and not folder.name.startswith('.'):
                    status["local_folders"] += 1
                    
                    # Check if it's tracked
                    if folder.name not in self.config["project_map"].values():
                        status["orphaned_folders"].append(folder.name)
        
        return status
    
    def list_projects(self) -> List[dict]:
        """List all tracked projects."""
        projects = []
        for project_id, folder_name in self.config["project_map"].items():
            folder_path = self.root / folder_name
            project_info = {
                "id": project_id,
                "folder": folder_name,
                "exists": folder_path.exists()
            }
            
            # Try to get more info from marker file
            info_file = folder_path / ".claudesync" / "project.json"
            if info_file.exists():
                with open(info_file, 'r') as f:
                    data = json.load(f)
                    project_info.update(data)
            
            projects.append(project_info)
        
        return projects