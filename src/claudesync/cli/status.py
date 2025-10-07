"""Status command for displaying project sync status."""

import click
import os
from datetime import datetime
from pathlib import Path

from ..metadatamanager import MetadataManager
from ..utils import handle_errors, validate_and_get_provider, get_local_files


def format_size(size_bytes):
    """Format byte size to human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB", "342 KB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            if unit == 'B':
                return f"{size_bytes:.0f} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def print_aligned_rows(rows):
    """Print rows with aligned labels and values.

    Args:
        rows: List of (label, value) tuples
    """
    if not rows:
        return

    max_label_width = max(len(label) for label, _ in rows)

    for label, value in rows:
        if label:
            padding = ' ' * (max_label_width - len(label) + 1)
            click.echo(f"{label}:{padding}{value}")
        else:
            # Empty label - no colon, just indent to align with values
            padding = ' ' * (max_label_width + 2)
            click.echo(f"{padding}{value}")


@click.command()
@click.pass_obj
@handle_errors
def status(config):
    """Display project status and sync information.

    Shows:
    - Project pairing status with organization
    - Last sync timestamp and direction
    - File and submodule counts
    """
    # Find the project root
    local_path = config.get_local_path()

    if not local_path:
        click.echo("Not a ClaudeSync project (no .claudesync directory found)")
        return

    # Load metadata with config to read project info
    metadata_manager = MetadataManager(local_path, config=config)

    # Check pairing status
    is_paired = metadata_manager.is_paired()
    project_name = metadata_manager.get_project_name()
    organization_id = metadata_manager.get_organization_id()

    # Get organization name if paired
    org_name = None
    if is_paired and organization_id:
        try:
            provider = validate_and_get_provider(config, require_project=False)
            organizations = provider.get_organizations()
            org_match = next((org for org in organizations if org['id'] == organization_id), None)
            if org_match:
                org_name = org_match['name']
        except Exception:
            pass  # Silently fail if we can't get org name

    # Build status rows
    status_rows = []

    # Status row
    if is_paired and project_name:
        if org_name:
            status_value = f"\033[32m●\033[0m Paired with project \"{project_name}\" ({org_name})"
        else:
            status_value = f"\033[32m●\033[0m Paired with project \"{project_name}\""
    else:
        status_value = "\033[31m●\033[0m Unpaired"
    status_rows.append(("Status", status_value))

    # Last sync row
    last_sync = metadata_manager.get_last_sync()
    last_sync_direction = metadata_manager.get_last_sync_direction()

    if last_sync:
        try:
            # Parse ISO format timestamp
            sync_time = datetime.fromisoformat(last_sync)
            formatted_time = sync_time.strftime("%Y-%m-%d %H:%M:%S")

            # Format direction
            direction_map = {
                "push": "Push",
                "pull": "Pull",
                "both": "Bidirectional"
            }
            direction_display = direction_map.get(last_sync_direction, last_sync_direction or "Unknown")
            sync_value = f"\033[32m●\033[0m {formatted_time} ({direction_display})"
        except ValueError:
            sync_value = f"\033[32m●\033[0m {last_sync}"
    else:
        sync_value = "\033[31m●\033[0m Unsynced"
    status_rows.append(("Last Sync", sync_value))

    # Add upload/download stats below Last Sync if available
    if last_sync:
        sync_history = metadata_manager.get_sync_history(limit=1)
        if sync_history:
            last_sync_record = sync_history[0]
            files_synced = last_sync_record.get('files_synced', 0)
            direction = last_sync_record.get('direction', '')

            # Determine upload/download counts based on direction
            if direction == 'push':
                uploaded = files_synced
                downloaded = 0
            elif direction == 'pull':
                uploaded = 0
                downloaded = files_synced
            elif direction == 'both':
                # For bidirectional, we show total as both
                uploaded = files_synced
                downloaded = files_synced
            else:
                uploaded = 0
                downloaded = 0

            # Build the stats line
            stats_parts = []
            if downloaded > 0:
                stats_parts.append(f"↓ {downloaded} file{'s' if downloaded != 1 else ''} downloaded")
            if uploaded > 0:
                stats_parts.append(f"↑ {uploaded} file{'s' if uploaded != 1 else ''} uploaded")

            if stats_parts:
                stats_line = ", ".join(stats_parts)
                status_rows.append(("", f"  {stats_line}"))

    print_aligned_rows(status_rows)

    # Only show file/submodule counts if paired
    if is_paired:
        click.echo()

        # Build count rows
        count_rows = []

        # Count local files and calculate total size
        try:
            local_files = get_local_files(config, local_path)
            file_count = len(local_files)

            # Calculate total size
            total_size = 0
            for file_path in local_files.keys():
                full_path = os.path.join(local_path, file_path)
                if os.path.exists(full_path):
                    total_size += os.path.getsize(full_path)

            size_str = format_size(total_size)
            count_rows.append(("Local Files", f"{file_count} ({size_str})"))
        except Exception as e:
            count_rows.append(("Local Files", f"Unable to count ({str(e)})"))

        # Count submodules
        submodules = config.get("submodules", [])
        submodule_count = len(submodules) if submodules else 0
        count_rows.append(("Submodules", str(submodule_count)))

        # Print count rows
        print_aligned_rows(count_rows)
