import os
import shutil

import click

from jam import helpers


@click.command(context_settings={"ignore_unknown_options": True})
@click.argument("repo")
@click.argument("filler", required=False, default=None)
@click.argument("new_name", required=False, default=None)
def copy(repo, filler, new_name):
    """Copy a repo as a new repo on GitHub.

    Usage:  jam copy REPO as NEW
            jam copy REPO          (prompts for new name)
    """
    # Validate the "as" filler word if provided
    if filler is not None and filler.lower() != "as":
        helpers.fail(f"Expected 'as', got '{filler}'. Usage: jam copy REPO as NEW")
    if filler is not None and new_name is None:
        helpers.fail("Missing new repo name. Usage: jam copy REPO as NEW")

    # Resolve source repo
    repo = helpers.match_repo(repo)
    jam_home = helpers.get_jam_home()
    src_path = os.path.join(jam_home, repo)

    # Prompt for name if not given
    if new_name is None:
        new_name = click.prompt("New repo name")

    user = helpers.get_gh_user()

    # Check new repo doesn't already exist
    result = helpers.run(f"gh repo view {user}/{new_name}")
    if result.returncode == 0:
        helpers.fail(f"Repo {user}/{new_name} already exists on GitHub.")

    dst_path = os.path.join(jam_home, new_name)
    if os.path.exists(dst_path):
        helpers.fail(f"Directory {dst_path} already exists.")

    # Create new repo on GitHub and clone it
    result = helpers.run(
        f"gh repo create {user}/{new_name} --private --clone", cwd=jam_home
    )
    if result.returncode != 0:
        helpers.fail(f"Failed to create repo: {result.stderr.strip()}")

    helpers.run("git checkout -b main", cwd=dst_path)

    # Copy files from source, excluding .git
    for entry in os.listdir(src_path):
        if entry == ".git":
            continue
        src = os.path.join(src_path, entry)
        dst = os.path.join(dst_path, entry)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    if helpers.get_jam_config("attribution_enabled"):
        helpers.write_repo_claude_settings(dst_path)

    helpers.run("git add -A", cwd=dst_path)
    helpers.run(f'git commit -m "copied from {repo}"', cwd=dst_path)
    helpers.run("git push -u origin main", cwd=dst_path)

    click.echo(f"Created {user}/{new_name} from {repo}")
