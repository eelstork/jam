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


def _usage_log_path():
    return os.path.join(_config_dir(), "usage.log")


def log_command(name):
    """Append a timestamped command invocation to the usage log."""
    from datetime import datetime
    path = _usage_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(f"{datetime.now().isoformat()} {name}\n")


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


def is_repo(name):
    """Return True if *name* uniquely matches a repo in JAM_HOME."""
    jam_home = get_jam_home()
    if os.path.isdir(os.path.join(jam_home, name)):
        return True
    try:
        entries = os.listdir(jam_home)
    except OSError:
        entries = []
    candidates = [
        d for d in entries
        if d.startswith(name) and os.path.isdir(os.path.join(jam_home, d))
    ]
    return len(candidates) == 1


def match_repo(name):
    """Resolve a possibly-incomplete repo name via prefix matching.

    Returns the full repo name.  Fails if *name* matches nothing or is
    ambiguous (matches more than one directory).
    """
    jam_home = get_jam_home()
    exact = os.path.join(jam_home, name)
    if os.path.isdir(exact):
        return name
    try:
        entries = os.listdir(jam_home)
    except OSError:
        entries = []
    candidates = sorted(
        d for d in entries
        if d.startswith(name) and os.path.isdir(os.path.join(jam_home, d))
    )
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        fail(f"Ambiguous repo name '{name}'. Matches: {', '.join(candidates)}")
    fail(f"Repo '{name}' not found.")


def resolve_repo(name=None):
    """Resolve repo path from NAME or current directory."""
    jam_home = os.path.realpath(get_jam_home())
    if name:
        name = match_repo(name)
        return os.path.join(jam_home, name)
    cwd = os.path.realpath(os.getcwd())
    if cwd == jam_home or cwd.startswith(jam_home + os.sep):
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


def _repo_claude_settings_path(repo_path):
    return os.path.join(repo_path, ".claude", "settings.json")


def _git_user_name(cwd=None):
    """Return the git user.name (local then global), or empty string."""
    result = run("git config user.name", cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_user_email(cwd=None):
    """Return the git user.email (local then global), or empty string."""
    result = run("git config user.email", cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def write_repo_claude_settings(repo_path):
    """Write .claude/settings.json into a repo to set attribution and SessionStart hook."""
    settings_path = _repo_claude_settings_path(repo_path)
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)
    if "attribution" not in settings:
        settings["attribution"] = {}
    git_name = _git_user_name(cwd=repo_path)
    git_email = _git_user_email(cwd=repo_path)
    settings["attribution"]["commit"] = git_name
    settings["attribution"]["pr"] = git_name
    # Add SessionStart hook to configure git identity
    settings["hooks"] = {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f'git config user.name "{git_name}" && git config user.email "{git_email}"',
                    }
                ]
            }
        ]
    }
    # Ensure $schema is first by rebuilding the dict with it at the top
    ordered = {"$schema": "https://json.schemastore.org/claude-code-settings.json"}
    ordered.update(settings)
    with open(settings_path, "w") as f:
        json.dump(ordered, f, indent=2)
    return settings_path


def repo_has_claude_settings(repo_path):
    """Check if a repo has .claude/settings.json with attribution and hooks configured."""
    settings_path = _repo_claude_settings_path(repo_path)
    if not os.path.exists(settings_path):
        return False
    with open(settings_path) as f:
        settings = json.load(f)
    has_attribution = "commit" in settings.get("attribution", {})
    has_hooks = bool(settings.get("hooks", {}).get("SessionStart"))
    return has_attribution and has_hooks


def ensure_repo_claude_settings(repo_path):
    """Ensure .claude/settings.json is complete; write and commit if needed.

    Returns True on success (or nothing to do), False on failure.
    """
    if not get_jam_config("attribution_enabled"):
        return True
    if repo_has_claude_settings(repo_path):
        return True
    write_repo_claude_settings(repo_path)
    for cmd in [
        "git add .claude/settings.json",
        'git commit -m "update .claude/settings.json"',
    ]:
        result = run(cmd, cwd=repo_path)
        if result.returncode != 0:
            return False
    return True
