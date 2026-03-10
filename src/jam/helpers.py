import json
import os
import subprocess
import sys

import click


def run(cmd, **kwargs):
    """Run a shell command and return the result."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def get_head(repo_path):
    """Get current HEAD sha."""
    result = run("git rev-parse HEAD", cwd=repo_path)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _breadcrumb_path(repo_path):
    return os.path.join(repo_path, ".git", "jam-undo.json")


def save_breadcrumb(repo_path, action, **data):
    """Save an undo breadcrumb for a repo."""
    crumb = {"action": action, **data}
    path = _breadcrumb_path(repo_path)
    with open(path, "w") as f:
        json.dump(crumb, f)


def load_breadcrumb(repo_path):
    """Load the last undo breadcrumb, or None."""
    path = _breadcrumb_path(repo_path)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def clear_breadcrumb(repo_path):
    """Remove the undo breadcrumb."""
    path = _breadcrumb_path(repo_path)
    if os.path.exists(path):
        os.remove(path)


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
