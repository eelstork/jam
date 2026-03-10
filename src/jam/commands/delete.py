import os
import shutil

import click

from jam import helpers


@click.command()
@click.argument("name")
def delete(name):
    """Delete a repo locally. Tags the remote for later cleanup."""
    jam_home = helpers.get_jam_home()
    repo_path = os.path.join(jam_home, name)

    if not os.path.isdir(repo_path):
        helpers.fail(f"Repo {name} not found at {repo_path}")

    if not click.confirm(f"Delete local copy of {name}?"):
        click.echo("Aborted.")
        return

    # Tag the remote so we can clean up later with `jam purge`
    helpers.run(f"git tag jam-delete", cwd=repo_path)
    helpers.run(f"git push origin tag jam-delete", cwd=repo_path)

    shutil.rmtree(repo_path)

    click.echo(f"Deleted {name} locally. Remote tagged for cleanup (jam purge).")
