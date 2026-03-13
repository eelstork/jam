import os
import shutil

import click

from jam import helpers


@click.command()
@click.argument("source")
@click.argument("target")
@click.argument("description", default="")
@click.option("--public", is_flag=True, help="Create a public repo.")
def clone(source, target, description, public):
    """Clone a repo as a new repo."""
    jam_home = helpers.get_jam_home()
    user = helpers.get_gh_user()

    source_path = os.path.join(jam_home, source)
    if not os.path.isdir(source_path):
        helpers.fail(f"Source repo {source} not found at {source_path}")

    result = helpers.run(f"gh repo view {user}/{target}")
    if result.returncode == 0:
        helpers.fail(f"Repo {user}/{target} already exists.")

    target_path = os.path.join(jam_home, target)
    if os.path.exists(target_path):
        helpers.fail(f"Directory {target_path} already exists.")

    shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns(".git"))

    helpers.run("git init", cwd=target_path)
    helpers.run("git checkout -b main", cwd=target_path)

    visibility = "--public" if public else "--private"
    result = helpers.run(f"gh repo create {user}/{target} {visibility}", cwd=target_path)
    if result.returncode != 0:
        helpers.fail(f"Failed to create repo: {result.stderr.strip()}")

    helpers.run(f"git remote add origin https://github.com/{user}/{target}.git", cwd=target_path)

    readme_path = os.path.join(target_path, "README.md")
    desc = description if description else "no description yet"
    with open(readme_path, "w") as f:
        f.write(f"# {target}\n\n{desc}\n")

    if helpers.get_jam_config("attribution_enabled"):
        helpers.write_repo_claude_settings(target_path)

    helpers.run("git add -A", cwd=target_path)
    helpers.run('git commit -m "initial commit"', cwd=target_path)
    helpers.run("git push -u origin main", cwd=target_path)

    click.echo(f"Cloned {source} as {user}/{target} at {target_path}")
