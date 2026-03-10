import os

import click

from jam import helpers


@click.command("set-root")
@click.argument("path")
def set_root(path):
    """Set the jam root directory."""
    resolved = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(resolved):
        helpers.fail(f"Directory does not exist: {resolved}")
    helpers.save_root(resolved)
    click.echo(f"Jam root set to {resolved}")
