import os

import click

from jam import helpers


@click.command()
@click.argument("name")
@click.argument("description", default="")
@click.option("--public", is_flag=True, help="Create a public repo.")
def new(name, description, public):
    """Create a new repo."""
    jam_home = helpers.get_jam_home()
    user = helpers.get_gh_user()

    result = helpers.run(f"gh repo view {user}/{name}")
    if result.returncode == 0:
        helpers.fail(f"Repo {user}/{name} already exists.")

    repo_path = os.path.join(jam_home, name)
    if os.path.exists(repo_path):
        helpers.fail(f"Directory {repo_path} already exists.")

    visibility = "--public" if public else "--private"
    result = helpers.run(f"gh repo create {user}/{name} {visibility} --clone", cwd=jam_home)
    if result.returncode != 0:
        helpers.fail(f"Failed to create repo: {result.stderr.strip()}")

    helpers.run(f"git checkout -b main", cwd=repo_path)

    readme_path = os.path.join(repo_path, "README.md")
    desc = description if description else "no description yet"
    with open(readme_path, "w") as f:
        f.write(f"# {name}\n\n{desc}\n")

    helpers.run("git add README.md", cwd=repo_path)
    helpers.run('git commit -m "initial commit"', cwd=repo_path)
    helpers.run("git push -u origin main", cwd=repo_path)

    click.echo(f"Created {user}/{name} at {repo_path}")
