import os
import sys

import click

from jam import helpers


@click.command()
def update():
    """Update jam to the latest version."""
    # Trace back from src/jam/commands/update.py -> repo root (4 levels)
    here = os.path.abspath(__file__)
    jam_repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))

    remote_url = "git+https://github.com/eelstork/jam.git"

    if not os.path.isdir(os.path.join(jam_repo, ".git")):
        click.echo(f"No local source found. Reinstalling from {remote_url}")
        result = helpers.run(
            f'"{sys.executable}" -m pip install --upgrade {remote_url}'
        )
        if result.returncode != 0:
            helpers.fail(f"pip install failed: {result.stderr.strip()}")
    else:
        click.echo(f"Updating from {jam_repo}")
        result = helpers.run("git pull", cwd=jam_repo)
        if result.returncode != 0:
            helpers.fail(f"git pull failed: {result.stderr.strip()}")

        click.echo("Installing...")
        result = helpers.run(
            f'"{sys.executable}" -m pip install -e .', cwd=jam_repo
        )
        if result.returncode != 0:
            helpers.fail(f"pip install failed: {result.stderr.strip()}")

    click.echo("Updated.")
