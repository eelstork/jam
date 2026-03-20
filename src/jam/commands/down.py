import os

import click

from jam import helpers


@click.command()
@click.argument("name", default="")
@click.option("--force", is_flag=True, help="Force pull (discard local changes).")
def down(name, force):
    """Pull latest changes, or clone from remote if not local."""
    if name and not helpers.is_repo(name):
        # Not found locally — try cloning from the user's GitHub
        jam_home = helpers.get_jam_home()
        user = helpers.get_gh_user()
        result = helpers.run(f"gh repo view {user}/{name}")
        if result.returncode != 0:
            helpers.fail(f"Repo '{name}' not found locally or on GitHub.")
        repo_path = os.path.join(jam_home, name)
        result = helpers.run(
            f"git clone https://github.com/{user}/{name}.git {repo_path}"
        )
        if result.returncode != 0:
            helpers.fail(f"git clone failed: {result.stderr.strip()}")
        click.echo(f"Cloned {user}/{name} into {repo_path}")
        return

    repo_path = helpers.resolve_repo(name or None)

    pre_head = helpers.get_head(repo_path)

    if force:
        helpers.run("git reset --hard HEAD", cwd=repo_path)

    result = helpers.run("git pull", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git pull failed: {result.stderr.strip()}")

    helpers.save_breadcrumb(repo_path, "down", pre_head=pre_head)
    click.echo("Pulled.")
