import os
import sys

import click

from jam import helpers


def _is_readme_only(repo_path):
    """Check if a local repo contains only a README (no other meaningful files).

    Checks both tracked files (git ls-files) and the working tree to catch
    repos with untracked content too.  Returns True only when every file
    is a README variant, .gitignore, or dotfile config like .claude/.
    """
    readme_names = {"README.md", "README", "README.txt", "readme.md"}
    ignorable = {".gitignore"}
    ignorable_dirs = {".git", ".claude", ".github"}

    # Walk the working tree — catches untracked files too
    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Skip ignorable dot-directories
        dirnames[:] = [d for d in dirnames if d not in ignorable_dirs]
        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), repo_path)
            if rel in readme_names or rel in ignorable:
                continue
            return False
    return True


def _find_readme_only_repos():
    """Return list of repo names in JAM_HOME that only have a README."""
    jam_home = helpers.get_jam_home()
    repos = []
    for entry in sorted(os.listdir(jam_home)):
        path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        if _is_readme_only(path):
            repos.append(entry)
    return repos


def _multi_pick(items, header=None):
    """Interactive multi-select picker.

    Arrow keys to navigate, x to toggle selection, enter to confirm.
    Returns list of selected indices, or None if user quit.
    """
    if not items:
        return None

    _WINDOWS = sys.platform == "win32"

    if _WINDOWS:
        import msvcrt
    else:
        import tty
        import termios

    def _read_key(fd):
        if _WINDOWS:
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                if code == "H":
                    return "up"
                if code == "P":
                    return "down"
                return ch
        else:
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    return "up"
                if seq == "[B":
                    return "down"
                return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "q":
            return "quit"
        return ch

    selected = set()
    cursor = 0

    if not _WINDOWS:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
    else:
        fd = None

    def _render():
        total = len(items) + (1 if header else 0)
        sys.stdout.write(f"\x1b[{total}A\r")
        if header:
            sys.stdout.write(f"\x1b[2K{header}\r\n")
        for i, item in enumerate(items):
            sys.stdout.write("\x1b[2K")
            mark = "x" if i in selected else " "
            if i == cursor:
                line = f"  \x1b[7m [{mark}] {item} \x1b[0m"
            else:
                line = f"   [{mark}] {item}"
            sys.stdout.write(line + "\r\n")
        sys.stdout.flush()

    def _clear():
        total = len(items) + (1 if header else 0)
        sys.stdout.write(f"\x1b[{total}A")
        for _ in range(total):
            sys.stdout.write("\x1b[2K\r\n")
        sys.stdout.write(f"\x1b[{total}A")
        sys.stdout.flush()

    try:
        if not _WINDOWS:
            tty.setraw(fd)
        total = len(items) + (1 if header else 0)
        sys.stdout.write("\r\n" * total)
        sys.stdout.flush()
        _render()

        while True:
            key = _read_key(fd)
            if key == "up":
                cursor = (cursor - 1) % len(items)
            elif key == "down":
                cursor = (cursor + 1) % len(items)
            elif key == "x":
                if cursor in selected:
                    selected.discard(cursor)
                else:
                    selected.add(cursor)
            elif key == "enter":
                _clear()
                return sorted(selected)
            elif key in ("quit", "esc"):
                _clear()
                return None
            _render()
    finally:
        if not _WINDOWS:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)



@click.command()
def prune():
    """Delete GitHub repos that only contain a README."""
    if not sys.stdin.isatty():
        helpers.fail("prune requires an interactive terminal.")

    jam_home = helpers.get_jam_home()
    click.echo("Scanning repos in jam home…\n")
    repos = _find_readme_only_repos()

    if not repos:
        click.echo("No readme-only repos found.")
        return

    click.echo(f"Found {len(repos)} readme-only repo(s).\n")

    while True:
        selected_indices = _multi_pick(
            repos, header="Select empty (readme only) repos to remove locally (↑↓ navigate, x toggle, enter confirm):"
        )

        if selected_indices is None or len(selected_indices) == 0:
            click.echo("Nothing selected.")
            return

        selected_names = [repos[i] for i in selected_indices]
        click.echo("Will delete:")
        for name in selected_names:
            click.echo(f"  {name}")

        choice = click.prompt(
            "\n[D]elete, [c]ancel, [r]eview",
            type=click.Choice(["d", "c", "r"], case_sensitive=False),
            default="d",
            show_choices=False,
        )

        if choice == "c":
            click.echo("Aborted.")
            return
        if choice == "r":
            click.echo()
            continue

        # choice == "y" — delete local only
        import shutil

        for name in selected_names:
            repo_path = os.path.join(jam_home, name)
            click.echo(f"Removing {name}…", nl=False)
            try:
                shutil.rmtree(repo_path)
            except PermissionError:
                def _on_rm_error(_func, path, _exc_info):
                    os.chmod(path, 0o700)
                    _func(path)
                shutil.rmtree(repo_path, onerror=_on_rm_error)
            click.echo(" done")

        click.echo(f"\nPruned {len(selected_names)} repo(s).")
        return
