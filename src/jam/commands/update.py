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

    if not os.path.isdir(os.path.join(jam_repo, ".git")):
        helpers.fail(
            f"jam source repo not found at {jam_repo}\n"
            f"Did you move or delete it? "
            f"Reinstall with: git clone <repo-url> && python install.py"
        )

    click.echo(f"Updating from {jam_repo}")
    result = helpers.run("git pull", cwd=jam_repo)
    if result.returncode != 0:
        helpers.fail(f"git pull failed: {result.stderr.strip()}")

    click.echo("Installing...")
    result = helpers.run(f"{sys.executable} -m pip install -e .", cwd=jam_repo)
    if result.returncode != 0:
        helpers.fail(f"pip install failed: {result.stderr.strip()}")

    click.echo("Updated.")
