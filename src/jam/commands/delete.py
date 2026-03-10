import os
import shutil

import click

from jam import helpers


@click.command()
@click.argument("name")
def delete(name):
    """Delete a repo locally and on GitHub."""
    jam_home = helpers.get_jam_home()
    user = helpers.get_gh_user()
    repo_path = os.path.join(jam_home, name)

    if not os.path.isdir(repo_path):
        helpers.fail(f"Repo {name} not found at {repo_path}")

    if not click.confirm(f"Delete {name}? This removes the local copy and the GitHub repo."):
        click.echo("Aborted.")
        return

    confirm = click.prompt(f"Type '{name}' to confirm")
    if confirm != name:
        click.echo("Name does not match. Aborted.")
        return

    result = helpers.run(f"gh repo delete {user}/{name} --yes")
    if result.returncode != 0:
        helpers.fail(f"Failed to delete GitHub repo: {result.stderr.strip()}")

    shutil.rmtree(repo_path)

    click.echo(f"Deleted {name}.")
