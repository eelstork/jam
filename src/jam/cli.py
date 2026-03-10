import os
import subprocess
import sys

import click


def run(cmd, **kwargs):
    """Run a shell command and return the result."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def fail(msg):
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


def get_jam_home():
    jam_home = os.environ.get("JAM_HOME")
    if not jam_home:
        fail("JAM_HOME is not set. Set it to your repos directory.")
    return jam_home


def get_gh_user():
    result = run("gh api user --jq .login")
    if result.returncode != 0:
        fail("Could not get GitHub user. Is gh authenticated?")
    return result.stdout.strip()


def resolve_repo(name=None):
    """Resolve repo path from NAME or current directory."""
    jam_home = get_jam_home()
    if name:
        repo_path = os.path.join(jam_home, name)
        if not os.path.isdir(repo_path):
            fail(f"Repo {name} not found at {repo_path}")
        return repo_path
    cwd = os.getcwd()
    if cwd.startswith(jam_home):
        return cwd
    fail("Not inside JAM_HOME. Provide a repo name.")


@click.group()
def main():
    """jam - fast and safe git repos"""
    pass


@main.command()
@click.argument("name")
@click.argument("description", default="")
@click.option("--public", is_flag=True, help="Create a public repo.")
def new(name, description, public):
    """Create a new repo."""
    jam_home = get_jam_home()
    user = get_gh_user()

    # Check if repo already exists on GitHub
    result = run(f"gh repo view {user}/{name}")
    if result.returncode == 0:
        fail(f"Repo {user}/{name} already exists.")

    # Check if directory already exists locally
    repo_path = os.path.join(jam_home, name)
    if os.path.exists(repo_path):
        fail(f"Directory {repo_path} already exists.")

    # Create the repo on GitHub
    visibility = "--public" if public else "--private"
    result = run(f"gh repo create {user}/{name} {visibility} --clone", cwd=jam_home)
    if result.returncode != 0:
        fail(f"Failed to create repo: {result.stderr.strip()}")

    # Ensure default branch is main
    run(f"git checkout -b main", cwd=repo_path)

    # Create README
    readme_path = os.path.join(repo_path, "README.md")
    desc = description if description else "no description yet"
    with open(readme_path, "w") as f:
        f.write(f"# {name}\n\n{desc}\n")

    # Commit and push
    run("git add README.md", cwd=repo_path)
    run('git commit -m "initial commit"', cwd=repo_path)
    run("git push -u origin main", cwd=repo_path)

    click.echo(f"Created {user}/{name} at {repo_path}")


@main.command()
@click.argument("source")
@click.argument("target")
@click.argument("description")
def clone(source, target, description):
    """Clone a repo as a new repo."""
    click.echo(f"Cloning {source} as {target}")


@main.command(name="list")
def list_repos():
    """List repos."""
    click.echo("Listing repos")


@main.command()
@click.argument("args", nargs=-1, required=True)
@click.option("--force", is_flag=True, help="Force push.")
def up(args, force):
    """Add all, commit, and push. Usage: jam up [NAME] MESSAGE"""
    if len(args) == 2:
        name, message = args
    elif len(args) == 1:
        name, message = None, args[0]
    else:
        fail("Usage: jam up [NAME] MESSAGE")

    repo_path = resolve_repo(name)

    result = run("git add -A", cwd=repo_path)
    if result.returncode != 0:
        fail(f"git add failed: {result.stderr.strip()}")

    result = run(f'git commit -m "{message}"', cwd=repo_path)
    if result.returncode != 0:
        fail(f"git commit failed: {result.stderr.strip()}")

    force_flag = "--force" if force else ""
    result = run(f"git push {force_flag}", cwd=repo_path)
    if result.returncode != 0:
        fail(f"git push failed: {result.stderr.strip()}")

    click.echo("Pushed.")


@main.command()
@click.argument("name", default="")
@click.option("--force", is_flag=True, help="Force pull (discard local changes).")
def down(name, force):
    """Pull latest changes. Usage: jam down [NAME]"""
    repo_path = resolve_repo(name or None)

    if force:
        run("git reset --hard HEAD", cwd=repo_path)

    result = run("git pull", cwd=repo_path)
    if result.returncode != 0:
        fail(f"git pull failed: {result.stderr.strip()}")

    click.echo("Pulled.")
