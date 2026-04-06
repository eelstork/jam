import sys

import click

from jam import helpers


def _is_readme_only(user, name):
    """Check if a GitHub repo contains only a README (no other meaningful files).

    Uses the default branch tree via gh api.  Returns True when every
    top-level entry is a README variant or a dotfile config dir like .claude/.
    """
    result = helpers.run(
        f"gh api repos/{user}/{name}/git/trees/HEAD --jq '.tree[].path'"
    )
    if result.returncode != 0:
        return False
    paths = [p.strip() for p in result.stdout.strip().splitlines() if p.strip()]
    if not paths:
        return True
    readme_names = {"README.md", "README", "README.txt", "readme.md"}
    ignorable = {".gitignore", ".claude", ".github"}
    for p in paths:
        if p in readme_names or p in ignorable:
            continue
        return False
    return True


def _fetch_readme_only_repos(user):
    """Return list of repo names owned by *user* that only have a README."""
    result = helpers.run(
        f"gh repo list {user} --limit 200 --json name --jq '.[].name'"
    )
    if result.returncode != 0:
        helpers.fail("Could not list repos. Is gh authenticated?")
    names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    readme_only = []
    for name in names:
        click.echo(f"  checking {name}…", nl=False)
        if _is_readme_only(user, name):
            readme_only.append(name)
            click.echo(" readme-only")
        else:
            click.echo(" has content")
    return readme_only


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

    user = helpers.get_gh_user()
    click.echo(f"Scanning repos for {user}…\n")
    repos = _fetch_readme_only_repos(user)

    if not repos:
        click.echo("No readme-only repos found.")
        return

    click.echo(f"\nFound {len(repos)} readme-only repo(s).\n")

    while True:
        selected_indices = _multi_pick(
            repos, header="Select repos to delete (↑↓ navigate, x toggle, enter confirm):"
        )

        if selected_indices is None or len(selected_indices) == 0:
            click.echo("Nothing selected.")
            return

        selected_names = [repos[i] for i in selected_indices]
        click.echo("Will delete:")
        for name in selected_names:
            click.echo(f"  {user}/{name}")

        choice = click.prompt(
            "\n[y] delete, [n] cancel, [r] review list",
            type=click.Choice(["y", "n", "r"], case_sensitive=False),
            default="y",
            show_choices=False,
        )

        if choice == "n":
            click.echo("Aborted.")
            return
        if choice == "r":
            click.echo()
            continue

        # choice == "y" — delete
        for name in selected_names:
            click.echo(f"Deleting {user}/{name}…", nl=False)
            result = helpers.run(f"gh repo delete {user}/{name} --yes")
            if result.returncode == 0:
                click.echo(" done")
            else:
                click.echo(f" FAILED: {result.stderr.strip()}")

        click.echo(f"\nPruned {len(selected_names)} repo(s).")
        return
