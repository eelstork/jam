import os

import click

from jam import helpers


def _is_ignored(path, repo_path):
    """Check if a path is ignored by git."""
    result = helpers.run(f"git check-ignore -q {path}", cwd=repo_path)
    return result.returncode == 0


def _print_tree(directory, repo_path, prefix, depth, max_depth):
    """Recursively print a directory tree, respecting .gitignore."""
    if depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return

    # Filter out .git and gitignored entries
    visible = []
    for name in entries:
        if name == ".git":
            continue
        full = os.path.join(directory, name)
        if _is_ignored(full, repo_path):
            continue
        visible.append((name, full))

    for i, (name, full) in enumerate(visible):
        is_last = i == len(visible) - 1
        connector = "└── " if is_last else "├── "
        click.echo(f"{prefix}{connector}{name}")

        if os.path.isdir(full):
            extension = "    " if is_last else "│   "
            _print_tree(full, repo_path, prefix + extension, depth + 1, max_depth)


@click.command()
@click.argument("name", default="")
@click.option("-L", "level", type=int, default=2, help="Max display depth.")
def tree(name, level):
    """Show the directory tree for a repo."""
    repo_path = helpers.resolve_repo(name or None)
    click.echo(os.path.basename(repo_path))
    _print_tree(repo_path, repo_path, "", 0, level)
