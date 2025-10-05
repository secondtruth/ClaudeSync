import click

@click.command()
@click.option('--category', help='Specify the file category to sync')
@click.option('--uberproject', is_flag=True, help='Include submodules in parent project sync')
@click.option('--dryrun', is_flag=True, default=False, help='Just show what files would be sent')
@click.pass_context
def push(ctx, category, uberproject, dryrun):
    """Push files to Claude project (upload only).

    Equivalent to running 'csync sync --no-pull' for legacy workflows.
    """
    from .sync import sync
    return ctx.invoke(
        sync,
        conflict_strategy='local-wins',
        dry_run=dryrun,
        no_pull=True,
        no_push=False,
        category=category,
        uberproject=uberproject
    )
