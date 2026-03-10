import click

from jam import helpers


@click.command()
@click.argument("name", default="")
def undo(name):
    """Undo the last jam command on a repo."""
    repo_path = helpers.resolve_repo(name or None)

    crumb = helpers.load_breadcrumb(repo_path)
    if not crumb:
        helpers.fail("Nothing to undo.")

    action = crumb["action"]
    pre_head = crumb.get("pre_head")

    if action in ("up", "down", "land", "infuse"):
        if not pre_head:
            helpers.fail(f"Cannot undo {action}: no previous HEAD recorded.")

        result = helpers.run(f"git reset --hard {pre_head}", cwd=repo_path)
        if result.returncode != 0:
            helpers.fail(f"git reset failed: {result.stderr.strip()}")

        if action == "up":
            # Also force-push to undo the remote push
            result = helpers.run("git push --force", cwd=repo_path)
            if result.returncode != 0:
                click.echo(f"Warning: local reset done but push --force failed: {result.stderr.strip()}")

        if action == "land":
            result = helpers.run("git push --force", cwd=repo_path)
            if result.returncode != 0:
                click.echo(f"Warning: local reset done but push --force failed: {result.stderr.strip()}")

        helpers.clear_breadcrumb(repo_path)
        click.echo(f"Undid {action}. HEAD reset to {pre_head[:8]}.")
    else:
        helpers.fail(f"Don't know how to undo '{action}'.")
