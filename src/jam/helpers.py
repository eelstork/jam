import json
import os
import random
import subprocess
import sys

import click

JAM_EMOJI = ["\U0001f353", "\U0001f347", "\U0001fad0", "\U0001f36f"]  # 🍓🍇🫐🍯


def jam_emoji():
    """Return a random jam-related emoji."""
    return random.choice(JAM_EMOJI)


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


def git_repo_root():
    """Return the root of the current git repo, or None."""
    result = run("git rev-parse --show-toplevel")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def fail(msg):
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


def _config_dir():
    return os.path.join(os.path.expanduser("~"), ".config", "jam")


def _root_file():
    return os.path.join(_config_dir(), "root")


def find_jam_home():
    """Return the jam home directory, or None if not configured."""
    jam_home = os.environ.get("JAM_HOME")
    if not jam_home:
        root_file = _root_file()
        if os.path.exists(root_file):
            with open(root_file) as f:
                jam_home = f.read().strip()
    return jam_home or None


def get_jam_home():
    jam_home = find_jam_home()
    if not jam_home:
        fail("JAM_HOME is not set. Run jam set-root PATH or set the JAM_HOME env var.")
    return jam_home


def save_root(path):
    """Persist the jam root to ~/.config/jam/root."""
    config = _config_dir()
    os.makedirs(config, exist_ok=True)
    with open(_root_file(), "w") as f:
        f.write(path + "\n")


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


def _jam_config_path():
    return os.path.join(_config_dir(), "config.json")


def load_jam_config():
    """Read and return the jam config dict, or {} if missing."""
    path = _jam_config_path()
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_jam_config(**kwargs):
    """Merge kwargs into the existing config and write it back."""
    config = load_jam_config()
    config.update(kwargs)
    path = _jam_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def get_jam_config(key, default=None):
    """Convenience getter for a single config value."""
    return load_jam_config().get(key, default)
