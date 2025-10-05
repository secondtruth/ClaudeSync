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
from claudesync.utils import compute_md5_hash, get_local_files


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
        # Remove only filesystem-unsafe characters, preserve everything else including emojis
        # Windows forbidden: < > : " | ? * / \
        sanitized = re.sub(r'[<>:"|?*/\\]+', '', name)
        return sanitized.strip() or "unnamed_project"
    
    def sync_all(self, dry_run: bool = False, bidirectional: bool = False,
                 sync_chats: bool = False, conflict_strategy: str = "remote") -> Dict[str, int]:
        """
        Sync ALL projects from Claude.ai to local folders.
        Args:
            dry_run: Show what would be done without doing it
            bidirectional: Upload local changes to Claude.ai
            sync_chats: Also sync chat conversations
            conflict_strategy: How to resolve conflicts ('remote', 'local', 'newer', 'prompt')
        Returns stats: {created: N, updated: N, skipped: N, uploaded: N, conflicts: N}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0,
                 "uploaded": 0, "conflicts": 0, "chats": 0}
        
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
                        dry_run,
                        bidirectional,
                        conflict_strategy
                    )
                    if isinstance(result, dict):
                        for key, value in result.items():
                            stats[key] += value
                    else:
                        stats[result] += 1
                    pbar.update(1)

            # Sync chats if requested
            if sync_chats and not dry_run:
                chat_stats = self._sync_chats(active_org['id'], dry_run)
                stats['chats'] = chat_stats
            
        except Exception as e:
            print(f"X Sync failed: {e}")
            stats["errors"] += 1
        
        # Save updated config
        if not dry_run:
            self._save_config()
        
        return stats
    
    def _sync_project(self, org_id: str, project: dict, dry_run: bool,
                      bidirectional: bool = False, conflict_strategy: str = "remote"):
        """
        Sync individual project to folder.
        Returns: 'created', 'updated', 'skipped', 'errors', or dict of multiple stats
        """
        try:
            project_id = project['id']
            project_name = project['name']
            
            # Determine folder name
            if project_id in self.config["project_map"]:
                folder_name = self.config["project_map"][project_id]
            else:
                folder_name = self._sanitize_name(project_name)

                # Check if folder name already tracked in project_map for a different project
                reverse_map = {v: k for k, v in self.config["project_map"].items()}
                if folder_name in reverse_map and reverse_map[folder_name] != project_id:
                    # This folder name is already claimed by another project, find a unique suffix
                    base_name = folder_name
                    counter = 1
                    folder_name = f"{base_name}_{counter}"
                    while folder_name in reverse_map:
                        counter += 1
                        folder_name = f"{base_name}_{counter}"
                # If folder name not tracked or tracked for this project, use it (even if it exists on disk)
                # Don't save to project_map yet - wait until we verify actual folder name

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

            # Verify actual folder name created (filesystem may strip emojis/unicode)
            # Get the actual name from the directory listing
            actual_folder_name = folder_path.name

            # Update project_map with actual folder name if it's new or different
            if project_id not in self.config["project_map"] or self.config["project_map"][project_id] != actual_folder_name:
                self.config["project_map"][project_id] = actual_folder_name
            
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

            # Create context folder for knowledge files even if remote is empty so
            # bidirectional sync can reason about local-only changes.
            context_path = folder_path / "context"
            context_path.mkdir(exist_ok=True)

            # Download all files to context folder (AGENTS.md already handled above)
            for remote_file in remote_files:
                file_path = context_path / remote_file['file_name']

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
            
            # Bidirectional sync: upload local changes
            upload_stats = {"uploaded": 0, "conflicts": 0}
            if bidirectional and not dry_run:
                upload_stats = self._sync_local_to_remote(
                    org_id, project_id, folder_path,
                    remote_files, conflict_strategy
                )

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

            if bidirectional:
                result = {
                    "created": 1 if is_new else 0,
                    "updated": 0 if is_new else 1,
                    "uploaded": upload_stats["uploaded"],
                    "conflicts": upload_stats["conflicts"]
                }
                return result
            return "created" if is_new else "updated"
            
        except Exception as e:
            safe_print(f"  X Error syncing {project['name']}: {e}")
            return "errors"
    
    def _sync_local_to_remote(self, org_id: str, project_id: str, folder_path: Path,
                              remote_files: list, conflict_strategy: str) -> dict:
        """Upload local files to Claude.ai project."""
        stats = {"uploaded": 0, "conflicts": 0}

        # Handle AGENTS.md specially - upload as project instructions
        agents_path = folder_path / "AGENTS.md"
        if agents_path.exists():
            try:
                with open(agents_path, 'r', encoding='utf-8') as f:
                    instructions = f.read()
                self.provider.update_project_instructions(org_id, project_id, instructions)
                stats["uploaded"] += 1
            except Exception as e:
                safe_print(f"    Warning: Could not upload instructions: {e}")

        local_files = self._collect_local_files(folder_path)

        # Build remote file map and detect duplicates
        from collections import defaultdict
        remote_by_name = defaultdict(list)
        for f in remote_files:
            remote_by_name[f['file_name']].append(f)

        # Remove duplicate files on remote (keep newest by UUID)
        remote_map = {}
        for file_name, files in remote_by_name.items():
            if len(files) > 1:
                # Duplicates found - keep newest, delete rest
                files_sorted = sorted(files, key=lambda x: x['uuid'])
                to_keep = files_sorted[-1]
                to_delete = files_sorted[:-1]

                safe_print(f"    ⚠️  Found {len(files)} copies of '{file_name}', removing {len(to_delete)} duplicates")
                for dup in to_delete:
                    try:
                        self.provider.delete_file(org_id, project_id, dup['uuid'])
                    except Exception as e:
                        safe_print(f"      Warning: Could not delete duplicate: {e}")

                remote_map[file_name] = to_keep
            else:
                remote_map[file_name] = files[0]

        # Upload new or modified files
        for file_name, local_data in local_files.items():
            if file_name in remote_map:
                # File exists remotely - check for conflicts
                remote_hash = compute_md5_hash(remote_map[file_name]['content'])
                if local_data['hash'] != remote_hash:
                    # Conflict detected
                    if self._resolve_conflict(conflict_strategy, local_data, remote_map[file_name]):
                        # Upload local version
                        self.provider.upload_file(org_id, project_id, file_name, local_data['content'])
                        stats["uploaded"] += 1
                    stats["conflicts"] += 1
            else:
                # New file - upload it
                self.provider.upload_file(org_id, project_id, file_name, local_data['content'])
                stats["uploaded"] += 1

        # Delete remote files not in local (if strategy allows)
        if conflict_strategy in ["local", "newer"]:
            for remote_file in remote_files:
                if remote_file['file_name'] not in local_files:
                    self.provider.delete_file(org_id, project_id, remote_file['uuid'])

        return stats

    def _collect_local_files(self, folder_path: Path) -> Dict[str, Dict[str, str]]:
        """Collect local files that should be considered for uploads."""
        local_files: Dict[str, Dict[str, str]] = {}

        def add_file(file_path: Path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                return

            filename = file_path.name
            if filename in local_files:
                return

            local_files[filename] = {
                'content': content,
                'hash': compute_md5_hash(content)
            }

        context_path = folder_path / "context"
        if context_path.exists():
            for file_path in context_path.glob("*"):
                if file_path.is_file():
                    if ".claudesync" in str(file_path):
                        continue
                    if "chats" in str(file_path):
                        continue
                    add_file(file_path)

        for file_path in folder_path.glob("*"):
            if not file_path.is_file():
                continue
            if file_path.name == "AGENTS.md":
                continue
            if file_path.name.startswith('.'):
                continue
            add_file(file_path)

        return local_files

    def _resolve_conflict(self, strategy: str, local_data: dict, remote_file: dict) -> bool:
        """
        Resolve sync conflict based on strategy.
        Returns True to upload local, False to keep remote.
        """
        if strategy == "local":
            return True
        elif strategy == "remote":
            return False
        elif strategy == "newer":
            # Would need timestamps - for now prefer local
            return True
        elif strategy == "prompt":
            # For automation, default to remote
            return False
        return False

    def _sync_chats(self, org_id: str, dry_run: bool) -> int:
        """Sync chat conversations to per-project /chats folders."""
        try:
            conversations = self.provider.get_chat_conversations(org_id)
            synced_count = 0

            for conv in conversations:
                try:
                    chat_data = self.provider.get_chat_conversation(org_id, conv['uuid'])

                    # Determine project folder (use project_uuid if available)
                    project_id = conv.get('project_uuid') or chat_data.get('project_uuid')

                    if project_id and project_id in self.config.get("project_map", {}):
                        # Save to project's chats folder
                        folder_name = self.config["project_map"][project_id]
                        project_chats_dir = self.root / folder_name / "chats"
                    else:
                        # Fallback to global chats folder for chats without project
                        project_chats_dir = self.root / "claude_chats"

                    if not dry_run:
                        project_chats_dir.mkdir(parents=True, exist_ok=True)

                        # Save as markdown
                        chat_file = project_chats_dir / f"{self._sanitize_name(conv.get('name', conv['uuid']))}.md"
                        with open(chat_file, 'w', encoding='utf-8') as f:
                            f.write(f"# {conv.get('name', 'Untitled Chat')}\n\n")
                            f.write(f"**Created**: {conv.get('created_at', 'Unknown')}\n\n")

                            # Write messages (simplified)
                            if 'chat_messages' in chat_data:
                                for msg in chat_data['chat_messages']:
                                    sender = msg.get('sender', 'Unknown')
                                    text = msg.get('text', '')
                                    f.write(f"## {sender}\n\n{text}\n\n---\n\n")

                    synced_count += 1

                except Exception as e:
                    safe_print(f"    Warning: Could not sync chat {conv.get('name', 'Unknown')}: {e}")

            return synced_count
        except Exception as e:
            safe_print(f"    Warning: Could not sync chats: {e}")
            return 0

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

    def analyze_diff(self, provider, detailed: bool = False) -> dict:
        """
        Analyze differences between local workspace and remote Claude.ai projects.
        Returns detailed diff information.
        """
        diff_info = {
            "summary": {},
            "remote_only": [],
            "local_only": [],
            "matched": []
        }

        # Get remote projects
        orgs = provider.get_organizations()
        if not orgs:
            raise ValueError("No organizations found")

        active_org = orgs[0]
        remote_projects = provider.get_projects(active_org['id'])

        # Get local folders
        local_folders = {}
        if self.root.exists():
            for folder in self.root.iterdir():
                if folder.is_dir() and not folder.name.startswith('.'):
                    # Skip special folders
                    if folder.name in ['claude_chats', '.claudesync']:
                        continue
                    local_folders[folder.name] = folder

        # Build mappings using project_map (which tracks project_id -> folder_name)
        project_map = self.config.get("project_map", {})

        # Reverse map: folder_name -> project_id
        folder_to_project_id = {folder_name: project_id for project_id, folder_name in project_map.items()}

        # Map remote projects by ID
        remote_by_id = {project['id']: project for project in remote_projects}

        # Find remote-only projects (projects not in local workspace)
        for project in remote_projects:
            project_id = project['id']
            # Check if this project is tracked in project_map
            if project_id not in project_map:
                project_info = {
                    "name": project['name'],
                    "id": project_id,
                    "sanitized_name": self._sanitize_name(project['name'])
                }

                # Get file count if detailed
                if detailed:
                    try:
                        files = provider.list_files(active_org['id'], project_id)
                        project_info['file_count'] = len(files)
                    except:
                        project_info['file_count'] = 0

                diff_info['remote_only'].append(project_info)

        # Find local-only folders (folders not tracked in project_map)
        for folder_name in local_folders:
            if folder_name not in folder_to_project_id:
                diff_info['local_only'].append(folder_name)

        # Analyze matched projects (tracked in project_map AND exist locally)
        for project_id, folder_name in project_map.items():
            if folder_name in local_folders and project_id in remote_by_id:
                project = remote_by_id[project_id]
                folder_path = local_folders[folder_name]
                match_info = {
                    "name": project['name'],
                    "id": project['id'],
                    "folder": folder_name,
                    "has_differences": False,
                    "remote_only_files": [],
                    "local_only_files": [],
                    "modified_files": []
                }

                if detailed:
                    # Get remote files
                    try:
                        remote_files = provider.list_files(active_org['id'], project['id'])
                        remote_file_map = {f['file_name']: f for f in remote_files}
                    except:
                        remote_file_map = {}

                    # Get local files from context folder
                    local_file_map = {}
                    context_path = folder_path / "context"
                    if context_path.exists():
                        for file_path in context_path.glob("*"):
                            if file_path.is_file():
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = f.read()
                                    local_file_map[file_path.name] = {
                                        'path': file_path,
                                        'hash': compute_md5_hash(content)
                                    }
                                except:
                                    pass

                    # Check AGENTS.md
                    agents_path = folder_path / "AGENTS.md"
                    if agents_path.exists():
                        # AGENTS.md is handled separately, not in files
                        pass

                    # Find differences
                    for filename, remote_file in remote_file_map.items():
                        if filename not in local_file_map:
                            match_info['remote_only_files'].append(filename)
                            match_info['has_differences'] = True
                        else:
                            # Check if content matches
                            remote_hash = compute_md5_hash(remote_file['content'])
                            if local_file_map[filename]['hash'] != remote_hash:
                                match_info['modified_files'].append(filename)
                                match_info['has_differences'] = True

                    for filename in local_file_map:
                        if filename not in remote_file_map:
                            match_info['local_only_files'].append(filename)
                            match_info['has_differences'] = True

                diff_info['matched'].append(match_info)

        # Summary
        diff_info['summary'] = {
            "remote_projects": len(remote_projects),
            "local_folders": len(local_folders),
            "matched": len(diff_info['matched']),
            "remote_only": len(diff_info['remote_only']),
            "local_only": len(diff_info['local_only'])
        }

        return diff_info
