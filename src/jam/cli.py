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
@click.argument("description", default="")
@click.option("--public", is_flag=True, help="Create a public repo.")
def clone(source, target, description, public):
    """Clone a repo as a new repo. Usage: jam clone SOURCE TARGET [DESCRIPTION]"""
    jam_home = get_jam_home()
    user = get_gh_user()

    # Resolve source repo
    source_path = os.path.join(jam_home, source)
    if not os.path.isdir(source_path):
        fail(f"Source repo {source} not found at {source_path}")

    # Check target doesn't exist
    result = run(f"gh repo view {user}/{target}")
    if result.returncode == 0:
        fail(f"Repo {user}/{target} already exists.")

    target_path = os.path.join(jam_home, target)
    if os.path.exists(target_path):
        fail(f"Directory {target_path} already exists.")

    # Copy the repo contents (without .git)
    import shutil
    shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns(".git"))

    # Init fresh git repo
    run("git init", cwd=target_path)
    run("git checkout -b main", cwd=target_path)

    # Create the remote repo
    visibility = "--public" if public else "--private"
    result = run(f"gh repo create {user}/{target} {visibility}", cwd=target_path)
    if result.returncode != 0:
        fail(f"Failed to create repo: {result.stderr.strip()}")

    # Set remote
    run(f"git remote add origin https://github.com/{user}/{target}.git", cwd=target_path)

    # Update README
    readme_path = os.path.join(target_path, "README.md")
    desc = description if description else "no description yet"
    with open(readme_path, "w") as f:
        f.write(f"# {target}\n\n{desc}\n")

    # Commit and push
    run("git add -A", cwd=target_path)
    run('git commit -m "initial commit"', cwd=target_path)
    run("git push -u origin main", cwd=target_path)

    click.echo(f"Cloned {source} as {user}/{target} at {target_path}")


@main.command(name="list")
@click.option("--info", is_flag=True, help="Show description from README.")
def list_repos(info):
    """List repos."""
    jam_home = get_jam_home()
    for entry in sorted(os.listdir(jam_home)):
        path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        if not info:
            click.echo(entry)
            continue
        readme_path = os.path.join(path, "README.md")
        desc = ""
        if os.path.isfile(readme_path):
            with open(readme_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        desc = line
                        break
        if desc:
            click.echo(f"{entry} \u2014 {desc}")
        else:
            click.echo(entry)


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


@main.command()
@click.argument("name", default="")
@click.option("--all", "show_all", is_flag=True, help="Show all commits.")
@click.option("--fast", is_flag=True, help="Land without confirmation.")
def land(name, show_all, fast):
    """Merge the latest branch into main."""
    repo_path = resolve_repo(name or None)

    # Fetch latest
    result = run("git fetch --all", cwd=repo_path)
    if result.returncode != 0:
        fail(f"git fetch failed: {result.stderr.strip()}")

    # Find the most recently modified branch (not main)
    result = run(
        "git for-each-ref --sort=-committerdate refs/remotes/origin/ "
        "--format=%(refname:short)",
        cwd=repo_path,
    )
    if result.returncode != 0:
        fail(f"Failed to list branches: {result.stderr.strip()}")

    branches = [
        b.strip() for b in result.stdout.strip().splitlines()
        if b.strip() and b.strip() not in ("origin/main", "origin/HEAD")
    ]
    if not branches:
        fail("No branches to land.")

    branch = branches[0]
    local_branch = branch.replace("origin/", "", 1)

    # Get commits ahead of main
    result = run(
        f"git log origin/main..{branch} --oneline",
        cwd=repo_path,
    )
    if result.returncode != 0:
        fail(f"Failed to get commits: {result.stderr.strip()}")

    commits = result.stdout.strip().splitlines()
    if not commits:
        fail(f"No new commits on {branch}.")

    n = len(commits)

    if fast:
        # Silent mode
        pass
    else:
        # Show commits
        click.echo(f"Landing {branch} ({n} commit{'s' if n != 1 else ''}):")
        click.echo()
        display = commits if show_all else commits[:3]
        for c in display:
            click.echo(f"  {c}")
        if not show_all and n > 3:
            click.echo(f"  ... and {n - 3} more")
        click.echo()
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    # Merge into main
    run("git checkout main", cwd=repo_path)
    result = run(f"git merge {branch}", cwd=repo_path)
    if result.returncode != 0:
        fail(f"Merge failed: {result.stderr.strip()}")

    result = run("git push", cwd=repo_path)
    if result.returncode != 0:
        fail(f"git push failed: {result.stderr.strip()}")

    # Delete the branch
    run(f"git branch -d {local_branch}", cwd=repo_path)
    run(f"git push origin --delete {local_branch}", cwd=repo_path)

    click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch}.")


@main.command()
@click.argument("args", nargs=-1, required=True)
def infuse(args):
    """Copy files from one repo into another.

    Usage:
        jam infuse NAME into TARGET
        jam infuse SRC              (when inside a repo)
    """
    import shutil

    jam_home = get_jam_home()

    if len(args) == 3 and args[1] == "into":
        src_name, _, target_name = args
        src_path = os.path.join(jam_home, src_name)
        target_path = os.path.join(jam_home, target_name)
        if not os.path.isdir(src_path):
            fail(f"Repo {src_name} not found at {src_path}")
        if not os.path.isdir(target_path):
            fail(f"Repo {target_name} not found at {target_path}")
    elif len(args) == 1:
        src_name = args[0]
        src_path = os.path.join(jam_home, src_name)
        if not os.path.isdir(src_path):
            fail(f"Repo {src_name} not found at {src_path}")
        target_path = resolve_repo(None)
        target_name = os.path.basename(target_path)
    else:
        fail("Usage: jam infuse NAME into TARGET, or jam infuse SRC (inside a repo)")

    # Collect files from source (skip .git)
    conflicts = []
    to_copy = []
    for dirpath, dirnames, filenames in os.walk(src_path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fname in filenames:
            src_file = os.path.join(dirpath, fname)
            rel = os.path.relpath(src_file, src_path)
            dst_file = os.path.join(target_path, rel)
            if os.path.exists(dst_file):
                conflicts.append(rel)
            else:
                to_copy.append((src_file, dst_file))

    if conflicts:
        click.echo("Conflict — these files already exist in target:")
        for c in conflicts:
            click.echo(f"  {c}")
        fail(f"Cannot infuse {src_name} into {target_name} (conflicts).")

    if not to_copy:
        click.echo("Nothing to infuse.")
        return

    for src_file, dst_file in to_copy:
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.copy2(src_file, dst_file)

    click.echo(f"Infused {len(to_copy)} file{'s' if len(to_copy) != 1 else ''} from {src_name} into {target_name}.")
