"""Open a file in its default application."""

import os
import subprocess
import sys

import click

from jam import helpers
from jam.finder import find_file, _MAX_RESULTS


def _open_file(path):
    """Launch the OS default application for *path* without blocking."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@click.command()
@click.argument("filename")
@click.argument("repo", required=False, default=None)
def edit(filename, repo):
    """Open a file in its default application."""
    jam_home = helpers.get_jam_home()

    if repo:
        repo_path = os.path.join(jam_home, repo)
        if not os.path.isdir(repo_path):
            helpers.fail(f"Repo {repo} not found.")
        roots = [repo_path]
    else:
        roots = sorted(
            os.path.join(jam_home, d)
            for d in os.listdir(jam_home)
            if os.path.isdir(os.path.join(jam_home, d, ".git"))
        )

    results = find_file(filename, roots)

    if not results:
        helpers.fail(f"File '{filename}' not found.")

    if len(results) > _MAX_RESULTS:
        helpers.fail(f"Too many results for '{filename}'. Try specifying a repo.")

    if len(results) == 1:
        target = results[0]
    else:
        from jam.interactive import pick

        rel_paths = [os.path.relpath(p, jam_home) for p in results]
        idx = pick(rel_paths, header=f"Pick file to edit ({len(results)} matches)")
        if idx is None:
            return
        target = results[idx]

    _open_file(target)
    click.echo(os.path.relpath(target, jam_home))
