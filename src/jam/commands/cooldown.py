"""jam cooldown — Show today's commits across all repos."""

import os
from datetime import datetime

import click

from jam import helpers


@click.command()
def cooldown():
    """List today's commits (since 7 am) per repo."""
    jam_home = helpers.get_jam_home()
    since = datetime.now().replace(hour=7, minute=0, second=0).strftime("%Y-%m-%d %H:%M")

    found_any = False
    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            continue
        result = helpers.run(
            f'git log main --oneline --since="{since}"',
            cwd=repo_path,
        )
        lines = result.stdout.strip()
        if not lines:
            continue
        found_any = True
        commits = lines.splitlines()
        click.echo(f"{entry} ({len(commits)})")
        for line in commits:
            click.echo(f"  {line}")

    if not found_any:
        click.echo("No commits since 7 am today.")
