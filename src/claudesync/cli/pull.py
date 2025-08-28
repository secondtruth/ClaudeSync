import click

@click.command()
@click.option("-l", "--local-path", default=".", help="The local directory to pull to.")
@click.option("--dry-run", is_flag=True, help="Show what would be pulled without making changes.")
@click.option("--force", is_flag=True, help="Force pull, overwriting local changes.")
@click.option("--merge", is_flag=True, help="Merge remote changes with local (detect conflicts).")
@click.pass_context
def pull(ctx, local_path, dry_run, force, merge):
    """Pull files from Claude project to local directory (download only).
    
    This is a convenience wrapper for 'csync sync --no-push'.
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
        no_push=True  # This makes it PULL only
    )

@click.command()
@click.option('--category', help='Specify the file category to sync')
@click.option('--uberproject', is_flag=True, help='Include submodules in parent project sync')
@click.option('--dryrun', is_flag=True, default=False, help='Just show what files would be sent')
@click.pass_context
def push(ctx, category, uberproject, dryrun):
    """Push files to Claude project (upload only).
    
    This is a convenience wrapper for 'csync sync --no-pull'.
    """
    from .sync import sync
    return ctx.invoke(
        sync,
        conflict_strategy='local-wins',
        dry_run=dryrun,
        no_pull=True,  # This makes it PUSH only
        no_push=False,
        category=category,
        uberproject=uberproject
    )

@click.command()
@click.option('--interval', type=int, default=5, help='Sync interval in minutes')
@click.option('--remove', is_flag=True, help='Remove scheduled sync')
@click.pass_obj
def schedule(config, interval, remove):
    """Schedule automatic sync at regular intervals."""
    import platform
    import subprocess
    
    if remove:
        click.echo("Removing scheduled sync...")
        if platform.system() == "Windows":
            subprocess.run(["schtasks", "/Delete", "/TN", "ClaudeSync", "/F"])
        else:
            from python_crontab import CronTab
            cron = CronTab(user=True)
            cron.remove_all(comment='ClaudeSync')
            cron.write()
        click.echo("✅ Scheduled sync removed")
        return
    
    click.echo(f"Setting up sync every {interval} minutes...")
    
    if platform.system() == "Windows":
        # Windows Task Scheduler
        cmd = f'schtasks /Create /SC MINUTE /MO {interval} /TN "ClaudeSync" /TR "csync sync" /F'
        subprocess.run(cmd, shell=True)
    else:
        # Unix cron
        from python_crontab import CronTab
        cron = CronTab(user=True)
        cron.remove_all(comment='ClaudeSync')
        job = cron.new(command='csync sync', comment='ClaudeSync')
        job.minute.every(interval)
        cron.write()
    
    click.echo(f"✅ Scheduled sync every {interval} minutes")
