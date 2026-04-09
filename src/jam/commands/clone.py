import os

import click

from jam import helpers


@click.command()
@click.argument("name")
def clone(name):
    """Clone a repo from GitHub into the local jam root."""
    if helpers.is_repo(name):
        helpers.fail(f"Repo '{name}' already exists locally.")

    jam_home = helpers.get_jam_home()
    user = helpers.get_gh_user()

    repo_path = os.path.join(jam_home, name)
    result = helpers.run(
        f"git clone https://github.com/{user}/{name}.git {repo_path}"
    )
    if result.returncode != 0:
        helpers.fail(f"Could not clone '{name}': {result.stderr.strip()}")

    click.echo(f"Cloned {user}/{name} into {repo_path}")
