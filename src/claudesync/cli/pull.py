import click

@click.command()
@click.option("-l", "--local-path", default=".", help="The local directory to pull to.")
@click.option("--dry-run", is_flag=True, help="Show what would be pulled without making changes.")
@click.option("--force", is_flag=True, help="Force pull, overwriting local changes.")
@click.option("--merge", is_flag=True, help="Merge remote changes with local (detect conflicts).")
@click.pass_context
def pull(ctx, local_path, dry_run, force, merge):
    """Pull files from Claude project to local directory (download only).

    Equivalent to running 'csync sync --no-push' for legacy workflows.
    """
    # Map force/merge to conflict strategy
    conflict_strategy = 'remote-wins' if force else ('prompt' if merge else 'prompt')

    # Redirect to sync with PULL direction (no-push flag)
    from .sync import sync
    return ctx.invoke(
        sync,
        conflict_strategy=conflict_strategy,
        dry_run=dry_run,
        no_pull=False,
        no_push=True,
        category=None,
        uberproject=False
    )
