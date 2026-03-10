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
