import click

@click.command()
@click.option('--interval', type=int, default=5, help='Sync interval in minutes')
@click.option('--remove', is_flag=True, help='Remove scheduled sync')
@click.pass_obj
def schedule(config, interval, remove):
    """Schedule automatic sync at regular intervals."""
    import platform
    import subprocess

    if remove:
        click.echo('Removing scheduled sync...')
        if platform.system() == 'Windows':
            subprocess.run(['schtasks', '/Delete', '/TN', 'ClaudeSync', '/F'])
        else:
            from python_crontab import CronTab
            cron = CronTab(user=True)
            cron.remove_all(comment='ClaudeSync')
            cron.write()
        click.echo('Done. Scheduled sync removed')
        return

    click.echo(f'Setting up sync every {interval} minutes...')

    if platform.system() == 'Windows':
        cmd = f'schtasks /Create /SC MINUTE /MO {interval} /TN "ClaudeSync" /TR "csync sync" /F'
        subprocess.run(cmd, shell=True)
    else:
        from python_crontab import CronTab
        cron = CronTab(user=True)
        cron.remove_all(comment='ClaudeSync')
        job = cron.new(command='csync sync', comment='ClaudeSync')
        job.minute.every(interval)
        cron.write()

    click.echo(f'Done. Scheduled sync every {interval} minutes')
