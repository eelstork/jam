"""Run a repo-root script as a jam subcommand."""

import os
import subprocess
import sys

import click

from jam import helpers

# Extensions in preferred order per platform.
# The last entry on each platform is the "last resort" — only used if nothing
# else is available.
_WIN_ORDER = [".ps1", ".py", ".sh"]
_UNIX_ORDER = [".sh", ".py", ".ps1"]


def _is_windows():
    return sys.platform == "win32"


def _find_script(repo_root, name):
    """Find the best script for *name* at *repo_root*.

    Returns the full path, or None.
    """
    order = _WIN_ORDER if _is_windows() else _UNIX_ORDER
    preferred = order[:-1]  # native + cross-platform
    last_resort = order[-1]

    # Try preferred extensions first.
    for ext in preferred:
        path = os.path.join(repo_root, name + ext)
        if os.path.isfile(path):
            return path

    # Fall back to the "foreign" extension only if it is the sole option.
    path = os.path.join(repo_root, name + last_resort)
    if os.path.isfile(path):
        return path

    return None


def _build_argv(script_path):
    """Return the command list to execute *script_path*."""
    ext = os.path.splitext(script_path)[1].lower()
    if ext == ".py":
        return [sys.executable, script_path]
    if ext == ".ps1":
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]
    # .sh
    return ["bash", script_path]


def _repo_root_for(name):
    """If *name* is a repo in JAM_HOME, return its path. Otherwise None."""
    try:
        jam_home = helpers.get_jam_home()
    except SystemExit:
        return None
    repo_path = os.path.join(jam_home, name)
    if os.path.isdir(os.path.join(repo_path, ".git")):
        return repo_path
    return None


def make_command(cmd_name):
    """Create a Click command that resolves and runs a repo-root script."""

    @click.command(cmd_name, context_settings={"ignore_unknown_options": True,
                                               "allow_extra_args": True})
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cmd(args):
        args = list(args)

        # If the first arg is a repo name, run the script from that repo.
        repo_root = None
        if args:
            repo_root = _repo_root_for(args[0])
        if repo_root is not None:
            script = _find_script(repo_root, cmd_name)
            if script is None:
                helpers.fail(f"No script '{cmd_name}' in {args[0]}")
            extra = args[1:]
        else:
            # Fall back to the current git repo root.
            repo_root = helpers.git_repo_root()
            if repo_root is None:
                helpers.fail(f"Not in a git repo. Cannot run '{cmd_name}'.")
            script = _find_script(repo_root, cmd_name)
            if script is None:
                helpers.fail(f"No script '{cmd_name}' found at {repo_root}")
            extra = args

        argv = _build_argv(script) + extra
        result = subprocess.run(argv, cwd=repo_root)
        sys.exit(result.returncode)

    cmd.help = f"Run {cmd_name} script from repo root"
    return cmd
