import os
import sys

import click

from jam import helpers


@click.command()
def update():
    """Update jam to the latest version."""
    jam_repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    click.echo("Pulling latest changes...")
    result = helpers.run("git pull", cwd=jam_repo)
    if result.returncode != 0:
        helpers.fail(f"git pull failed: {result.stderr.strip()}")

    click.echo("Installing...")
    result = helpers.run(f"{sys.executable} -m pip install -e .", cwd=jam_repo)
    if result.returncode != 0:
        helpers.fail(f"pip install failed: {result.stderr.strip()}")

    click.echo("Updated.")
