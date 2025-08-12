import click
import os
import logging

from tqdm import tqdm
from ..provider_factory import get_provider
from ..utils import handle_errors, validate_and_get_provider
from ..exceptions import ProviderError, ConfigurationError
from .file import file
from .submodule import submodule
from ..syncmanager import retry_on_403
from ..project_selector import ProjectSelector
from ..project_instructions import ProjectInstructions

logger = logging.getLogger(__name__)


@click.group()
def project():
    """Manage AI projects within the active organization."""
    pass


@project.command()
@click.option(
    "--name",
    default=lambda: os.path.basename(os.getcwd()),
    prompt="Enter a title for your project",
    help="The name of the project (defaults to current directory name)",
    show_default="current directory name",
)
@click.option(
    "--description",
    default="Project created with ClaudeSync",
    prompt="Enter the project description",
    help="The project description",
    show_default=True,
)
@click.option(
    "--local-path",
    default=lambda: os.getcwd(),
    prompt="Enter the absolute path to your local project directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    help="The local path for the project (defaults to current working directory)",
    show_default="current working directory",
)
@click.option(
    "--new",
    is_flag=True,
    help="Create a new remote project on Claude.ai",
)
@click.option(
    "--provider",
    type=click.Choice(["claude.ai"], case_sensitive=False),
    default="claude.ai",
    help="The provider to use for this project",
)
@click.pass_context
@handle_errors
def init(ctx, name, description, local_path, new, provider):
    """Initialize a new project configuration.

    If --new is specified, also creates a remote project on Claude.ai.
    Otherwise, only creates the local configuration. Use 'csync organization set'
    and 'csync project set' to link to an existing remote project."""

    config = ctx.obj

    # Create .claudesync directory and save initial config
    claudesync_dir = os.path.join(local_path, ".claudesync")
    os.makedirs(claudesync_dir, exist_ok=True)

    # Set basic configuration
    config.set("active_provider", provider, local=True)
    config.set("local_path", local_path, local=True)

    if new:
        # Create remote project if --new flag is specified
        provider_instance = get_provider(config, provider)

        # Get organization
        organizations = provider_instance.get_organizations()
        if not organizations:
            raise ConfigurationError(
                "No organizations with required capabilities found."
            )
        organization = organizations[0]["id"]

        try:
            new_project = provider_instance.create_project(
                organization, name, description
            )
            click.echo(
                f"Project '{new_project['name']}' (uuid: {new_project['uuid']}) has been created successfully."
            )

            # Update configuration with remote details
            config.set("active_organization_id", organization, local=True)
            config.set("active_project_id", new_project["uuid"], local=True)
            config.set("active_project_name", new_project["name"], local=True)

            click.echo("\nProject created:")
            click.echo(f"  - Project location: {local_path}")
            click.echo(
                f"  - Project config location: {os.path.join(claudesync_dir, 'config.local.json')}"
            )
            click.echo(
                f"  - Remote URL: https://claude.ai/project/{new_project['uuid']}"
            )

        except (ProviderError, ConfigurationError) as e:
            click.echo(f"Failed to create remote project: {str(e)}")
            raise click.Abort()
    else:
        config._save_local_config()
        click.echo("\nLocal project configuration created:")
        click.echo(f"  - Project location: {local_path}")
        click.echo(
            f"  - Project config location: {os.path.join(claudesync_dir, 'config.local.json')}"
        )
        click.echo("\nTo link to a remote project:")
        click.echo("1. Run 'csync organization set' to select an organization")
        click.echo("2. Run 'csync project set' to select an existing project")


@project.command()
@click.pass_context
def create(ctx, **kwargs):
    """Create a new project (alias for 'init --new')."""
    # Forward to init command with --new flag
    ctx.forward(init, new=True)


@project.command()
@click.option(
    "-a",
    "--all",
    "archive_all",
    is_flag=True,
    help="Archive all active projects",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_obj
@handle_errors
def archive(config, archive_all, yes):
    """Archive existing projects."""
    provider = validate_and_get_provider(config)
    active_organization_id = config.get("active_organization_id")
    projects = provider.get_projects(active_organization_id, include_archived=False)

    if not projects:
        click.echo("No active projects found.")
        return

    if archive_all:
        if not yes:
            click.echo("The following projects will be archived:")
            for project in projects:
                click.echo(f"  - {project['name']} (ID: {project['id']})")
            if not click.confirm("Are you sure you want to archive all projects?"):
                click.echo("Operation cancelled.")
                return

        with click.progressbar(
            projects,
            label="Archiving projects",
            item_show_func=lambda p: p["name"] if p else "",
        ) as bar:
            for project in bar:
                try:
                    provider.archive_project(active_organization_id, project["id"])
                except Exception as e:
                    click.echo(
                        f"\nFailed to archive project '{project['name']}': {str(e)}"
                    )

        click.echo("\nArchive operation completed.")
        return

    single_project_archival(projects, yes, provider, active_organization_id)


def single_project_archival(projects, yes, provider, active_organization_id):
    click.echo("Available projects to archive:")
    for idx, project in enumerate(projects, 1):
        click.echo(f"  {idx}. {project['name']} (ID: {project['id']})")

    selection = click.prompt("Enter the number of the project to archive", type=int)
    if 1 <= selection <= len(projects):
        selected_project = projects[selection - 1]
        if yes or click.confirm(
            f"Are you sure you want to archive the project '{selected_project['name']}'? "
            f"Archived projects cannot be modified but can still be viewed."
        ):
            provider.archive_project(active_organization_id, selected_project["id"])
            click.echo(f"Project '{selected_project['name']}' has been archived.")
    else:
        click.echo("Invalid selection. Please try again.")


@project.command()
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    help="Include submodule projects in the selection",
)
@click.option(
    "--provider",
    type=click.Choice(["claude.ai"]),  # Add more providers as they become available
    default="claude.ai",
    help="Specify the provider for repositories without .claudesync",
)
@click.pass_context
@handle_errors
def set(ctx, show_all, provider):
    """Set the active project for syncing."""
    config = ctx.obj

    # If provider is not specified, try to get it from the config
    if not provider:
        provider = config.get("active_provider")

    # If provider is still not available, prompt the user
    if not provider:
        provider = click.prompt(
            "Please specify the provider",
            type=click.Choice(
                ["claude.ai"]
            ),  # Add more providers as they become available
        )

    # Update the config with the provider
    config.set("active_provider", provider, local=True)

    # Now we can get the provider instance
    provider_instance = validate_and_get_provider(config)
    active_organization_id = config.get("active_organization_id")
    active_project_name = config.get("active_project_name")
    projects = provider_instance.get_projects(
        active_organization_id, include_archived=False
    )

    if show_all:
        selectable_projects = projects
    else:
        # Filter out submodule projects
        selectable_projects = [p for p in projects if "-SubModule-" not in p["name"]]

    if not selectable_projects:
        click.echo("No active projects found.")
        return

    click.echo("Available projects:")
    for idx, project in enumerate(selectable_projects, 1):
        project_type = (
            "Main Project"
            if not project["name"].startswith(f"{active_project_name}-SubModule-")
            else "Submodule"
        )
        click.echo(f"  {idx}. {project['name']} (ID: {project['id']}) - {project_type}")

    selection = click.prompt(
        "Enter the number of the project to select", type=int, default=1
    )
    if 1 <= selection <= len(selectable_projects):
        selected_project = selectable_projects[selection - 1]
        config.set("active_project_id", selected_project["id"], local=True)
        config.set("active_project_name", selected_project["name"], local=True)
        click.echo(
            f"Selected project: {selected_project['name']} (ID: {selected_project['id']})"
        )

        # Create .claudesync directory in the current working directory if it doesn't exist
        os.makedirs(".claudesync", exist_ok=True)
        claudesync_dir = os.path.abspath(".claudesync")
        config_file_path = os.path.join(claudesync_dir, "config.local.json")
        config._save_local_config()

        click.echo("\nProject created:")
        click.echo(f"  - Project location: {os.getcwd()}")
        click.echo(f"  - Project config location: {config_file_path}")
    else:
        click.echo("Invalid selection. Please try again.")


@project.command()
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    help="Include archived projects in the list",
)
@click.pass_obj
@handle_errors
def ls(config, show_all):
    """List all projects in the active organization."""
    provider = validate_and_get_provider(config)
    active_organization_id = config.get("active_organization_id")
    projects = provider.get_projects(active_organization_id, include_archived=show_all)
    if not projects:
        click.echo("No projects found.")
    else:
        click.echo("Remote projects:")
        for project in projects:
            status = " (Archived)" if project.get("archived_at") else ""
            click.echo(f"  - {project['name']} (ID: {project['id']}){status}")


@project.command()
@click.option(
    "-a", "--include-archived", is_flag=True, help="Include archived projects"
)
@click.option("--all", "truncate_all", is_flag=True, help="Truncate all projects")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_obj
@handle_errors
def truncate(config, include_archived, truncate_all, yes):
    """Truncate one or all projects."""
    provider = validate_and_get_provider(config)
    active_organization_id = config.get("active_organization_id")

    projects = provider.get_projects(
        active_organization_id, include_archived=include_archived
    )

    if not projects:
        click.echo("No projects found.")
        return

    if truncate_all:
        if not yes:
            click.echo("This will delete ALL files from the following projects:")
            for project in projects:
                status = " (Archived)" if project.get("archived_at") else ""
                click.echo(f"  - {project['name']} (ID: {project['id']}){status}")
            if not click.confirm(
                "Are you sure you want to continue? This may take some time."
            ):
                click.echo("Operation cancelled.")
                return

        with tqdm(total=len(projects), desc="Deleting files from projects") as pbar:
            for project in projects:
                delete_files_from_project(
                    provider, active_organization_id, project["id"], project["name"]
                )
                pbar.update(1)

        click.echo("All files have been deleted from all projects.")
        return

    click.echo("Available projects:")
    for idx, project in enumerate(projects, 1):
        status = " (Archived)" if project.get("archived_at") else ""
        click.echo(f"  {idx}. {project['name']} (ID: {project['id']}){status}")

    selection = click.prompt("Enter the number of the project to truncate", type=int)
    if 1 <= selection <= len(projects):
        selected_project = projects[selection - 1]
        if yes or click.confirm(
            f"Are you sure you want to delete ALL files from project '{selected_project['name']}'?"
        ):
            delete_files_from_project(
                provider,
                active_organization_id,
                selected_project["id"],
                selected_project["name"],
            )
            click.echo(
                f"All files have been deleted from project '{selected_project['name']}'."
            )
    else:
        click.echo("Invalid selection. Please try again.")


@retry_on_403()
def delete_files_from_project(provider, organization_id, project_id, project_name):
    try:
        files = provider.list_files(organization_id, project_id)
        with tqdm(
            total=len(files), desc=f"Deleting files from {project_name}", leave=False
        ) as file_pbar:
            for current_file in files:
                provider.delete_file(organization_id, project_id, current_file["uuid"])
                file_pbar.update(1)
    except ProviderError as e:
        click.echo(f"Error deleting files from project {project_name}: {str(e)}")


@project.command()
@click.option('--multiple', '-m', is_flag=True, help='Select multiple projects')
@click.option('--include-archived', '-a', is_flag=True, help='Include archived projects')
@click.option('--search', '-s', help='Filter projects by search term')
@click.option('--sync-selected', is_flag=True, help='Sync selected projects immediately')
@click.pass_obj
@handle_errors
def select(config, multiple, include_archived, search, sync_selected):
    """Interactive project selection with filtering and actions."""
    provider = validate_and_get_provider(config)
    organization_id = config.get('active_organization_id')
    
    # Get all projects
    all_projects = provider.get_projects(organization_id, include_archived=True)
    
    # Filter projects
    filtered = ProjectSelector.filter_projects(
        all_projects, 
        search_term=search,
        include_archived=include_archived
    )
    
    if not filtered:
        click.echo("No projects found matching criteria.")
        return
    
    # Select projects
    if multiple:
        selected = ProjectSelector.select_multiple(
            filtered,
            prompt=f"Select projects to work with{' (filtered)' if search else ''}"
        )
    else:
        selected_project = ProjectSelector.select_single(
            filtered,
            prompt=f"Select a project{' (filtered)' if search else ''}"
        )
        selected = [selected_project] if selected_project else []
    
    if not selected:
        click.echo("No projects selected.")
        return
    
    # Display selected
    click.echo(f"\nSelected {len(selected)} project(s):")
    for project in selected:
        click.echo(f"  - {project['name']} (ID: {project['id']})")
    
    # Perform actions
    if sync_selected and len(selected) > 1:
        click.echo("\nSyncing selected projects...")
        
        import subprocess
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def sync_project(project):
            """Sync a single project."""
            try:
                # Find project directory
                # This would need workspace management to work properly
                # For now, we'll just show what would be synced
                return {
                    'project': project['name'],
                    'status': 'would_sync',
                    'message': 'Workspace management needed for multi-sync'
                }
            except Exception as e:
                return {
                    'project': project['name'],
                    'status': 'error',
                    'message': str(e)
                }
        
        # Sync in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(sync_project, p): p for p in selected}
            
            for future in as_completed(futures):
                result = future.result()
                if result['status'] == 'success':
                    click.echo(f"  ✓ {result['project']}")
                else:
                    click.echo(f"  ✗ {result['project']}: {result['message']}")
    
    elif sync_selected and len(selected) == 1:
        # Set as active and offer to sync
        project = selected[0]
        config.set('active_project_id', project['id'], local=True)
        config.set('active_project_name', project['name'], local=True)
        click.echo(f"\nSet active project: {project['name']}")
        
        if click.confirm("Sync this project now?"):
            subprocess.run(['csync', 'push'])


@project.group()
def instructions():
    """Manage project instructions for AI context."""
    pass

@instructions.command()
@click.option('--force', is_flag=True, help='Overwrite existing instructions file')
@click.pass_obj
@handle_errors
def init(config, force):
    """Initialize project instructions file."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured. Run 'claudesync project create' or 'set' first.")
        return
    
    instructions = ProjectInstructions(local_path)
    
    if instructions.initialize(force=force):
        click.echo(f"Created {instructions.INSTRUCTIONS_FILE} in {local_path}")
        click.echo("\nEdit this file to provide context for AI assistants.")
        click.echo("Use 'csync project instructions push' to sync to Claude.ai")
    else:
        click.echo(f"Project instructions file already exists: {instructions.INSTRUCTIONS_FILE}")
        click.echo("Use --force to overwrite.")

@instructions.command()
@click.pass_obj
@handle_errors
def pull(config):
    """Pull project instructions from Claude.ai."""
    provider = validate_and_get_provider(config, require_project=True)
    local_path = config.get('local_path')
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    
    click.echo("Pulling project instructions from Claude.ai...")
    if instructions.pull_instructions(provider, organization_id, project_id):
        click.echo(f"✓ Instructions saved to {instructions.INSTRUCTIONS_FILE}")
        
        # Show preview
        with open(os.path.join(local_path, instructions.INSTRUCTIONS_FILE), 'r') as f:
            content = f.read()
            if content.strip():
                click.echo("\nPreview:")
                preview = content[:200] + "..." if len(content) > 200 else content
                click.echo(preview)
            else:
                click.echo("\n(No instructions found in project)")
    else:
        click.echo("✗ Failed to pull instructions")

@instructions.command()
@click.pass_obj
@handle_errors
def push(config):
    """Push local instructions to Claude.ai project."""
    provider = validate_and_get_provider(config, require_project=True)
    local_path = config.get('local_path')
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    
    if not os.path.exists(os.path.join(local_path, instructions.INSTRUCTIONS_FILE)):
        click.echo(f"No {instructions.INSTRUCTIONS_FILE} found.")
        click.echo("Run 'csync project instructions init' first.")
        return
    
    click.echo("Pushing project instructions to Claude.ai...")
    if instructions.push_instructions(provider, organization_id, project_id):
        click.echo("✓ Instructions updated in Claude.ai project")
    else:
        click.echo("✗ Failed to push instructions")

@instructions.command()
@click.option('--direction', type=click.Choice(['pull', 'push', 'both']), default='both',
              help='Sync direction')
@click.pass_obj
@handle_errors
def sync(config, direction):
    """Sync project instructions with Claude.ai."""
    provider = validate_and_get_provider(config, require_project=True)
    local_path = config.get('local_path')
    organization_id = config.get('active_organization_id')
    project_id = config.get('active_project_id')
    
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    
    click.echo(f"Syncing project instructions ({direction})...")
    results = instructions.sync_instructions(provider, organization_id, project_id, direction)
    
    if direction in ["pull", "both"] and results["pulled"]:
        click.echo("✓ Pulled instructions from Claude.ai")
    
    if direction in ["push", "both"] and results["pushed"]:
        click.echo("✓ Pushed instructions to Claude.ai")
    
    if not any(results.values()):
        click.echo("✗ No instructions were synced")

@instructions.command()
@click.pass_obj
@handle_errors
def status(config):
    """Show project instructions status."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    status = instructions.get_status()
    
    click.echo("Project Instructions Status")
    click.echo("=" * 30)
    click.echo(f"Enabled: {'Yes' if status['enabled'] else 'No'}")
    click.echo(f"File: {status['path']}")
    click.echo(f"Exists: {'Yes' if status['exists'] else 'No'}")
    
    if status['exists']:
        click.echo(f"Size: {status['size']} bytes")
        click.echo(f"Modified: {status['modified']}")
        click.echo(f"Last synced: {status.get('last_synced', 'Never')}")
    
    if not status['enabled']:
        click.echo("\nUse 'csync project instructions enable' to activate syncing.")

@instructions.command()
@click.pass_obj
@handle_errors
def enable(config):
    """Enable project instructions syncing."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    instructions.enable()
    click.echo("Project instructions syncing enabled.")

@instructions.command()
@click.pass_obj
@handle_errors
def disable(config):
    """Disable project instructions syncing."""
    local_path = config.get('local_path')
    if not local_path:
        click.echo("No local path configured.")
        return
    
    instructions = ProjectInstructions(local_path)
    instructions.disable()
    click.echo("Project instructions syncing disabled.")


project.add_command(submodule)
project.add_command(file)

__all__ = ["project"]
