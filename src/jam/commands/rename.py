"""`jam rename REPO` — rename a repo locally and on GitHub."""

import os

import click

from jam import helpers


def _remote_repo_name(repo_path):
    """Return the origin remote's repo name, or None."""
    result = helpers.run("git config --get remote.origin.url", cwd=repo_path)
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    if not url:
        return None
    if url.endswith(".git"):
        url = url[:-4]
    return url.rsplit("/", 1)[-1].rsplit(":", 1)[-1] or None


@click.command()
@click.argument("repo")
def rename(repo):
    """Rename a repo locally and on GitHub.

    Usage:  jam rename REPO   (prompts for new name)
    """
    repo = helpers.match_repo(repo)
    jam_home = helpers.get_jam_home()
    repo_path = os.path.join(jam_home, repo)

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        helpers.fail(f"'{repo}' is not a git repo.")

    new_name = click.prompt("New name").strip()

    if not new_name:
        helpers.fail("New name is empty.")
    if new_name == repo:
        helpers.fail("New name is the same as the current name.")
    if "/" in new_name or " " in new_name:
        helpers.fail(f"Invalid name: '{new_name}'.")

    new_path = os.path.join(jam_home, new_name)
    if os.path.exists(new_path):
        helpers.fail(f"Directory already exists: {new_path}")

    remote_name = _remote_repo_name(repo_path)
    if remote_name is None:
        helpers.fail(f"'{repo}' has no origin remote.")
    if remote_name != repo:
        helpers.fail(
            f"Remote name '{remote_name}' does not match local name '{repo}'. "
            "Refusing to rename."
        )

    user = helpers.get_gh_user()
    if helpers.gh_repo_exists(user, new_name):
        helpers.fail(f"Repo {user}/{new_name} already exists on GitHub.")

    result = helpers.run(f"gh repo rename {new_name} --yes", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"GitHub rename failed: {result.stderr.strip()}")

    new_url = f"https://github.com/{user}/{new_name}.git"
    helpers.run(f"git remote set-url origin {new_url}", cwd=repo_path)

    os.rename(repo_path, new_path)

    click.echo(f"Renamed {repo} to {new_name}.")
