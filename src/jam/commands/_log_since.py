"""Shared helper for commands that show git log across all repos."""

import os

import click

from jam import helpers


def log_since(since_dt, empty_msg):
    """Print git log --oneline for all repos since the given datetime."""
    jam_home = helpers.get_jam_home()
    since = since_dt.strftime("%Y-%m-%d %H:%M")

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
        click.echo(empty_msg)
