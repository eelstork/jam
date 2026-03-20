import click

from jam import helpers


def _has_changes(repo_path):
    """Check if there are uncommitted or untracked changes."""
    result = helpers.run("git status --porcelain", cwd=repo_path)
    return bool(result.stdout.strip())


@click.command()
@click.argument("args", nargs=-1)
@click.option("--force", is_flag=True, help="Force push.")
def up(args, force):
    """Add all, commit, and push.

    Usage: jam up [REPO] [MESSAGE]

    If the first argument matches a known repo it is used as the repo name;
    otherwise it is treated as the commit message.
    """
    name = None
    message = ""

    if len(args) >= 1 and helpers.is_repo(args[0]):
        name = args[0]
        message = " ".join(args[1:]) if len(args) > 1 else ""
    else:
        message = " ".join(args) if args else ""

    repo_path = helpers.resolve_repo(name)

    pre_head = helpers.get_head(repo_path)

    has_changes = _has_changes(repo_path)

    if has_changes:
        if not message:
            message = click.prompt("Commit message")

        result = helpers.run("git add -A", cwd=repo_path)
        if result.returncode != 0:
            helpers.fail(f"git add failed: {result.stderr.strip()}")

        result = helpers.run(f'git commit -m "{message}"', cwd=repo_path)
        if result.returncode != 0:
            helpers.fail(f"git commit failed: {result.stderr.strip()}")

    force_flag = "--force" if force else ""
    result = helpers.run(f"git push {force_flag}", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git push failed: {result.stderr.strip()}")

    helpers.save_breadcrumb(repo_path, "up", pre_head=pre_head)
    click.echo("Pushed.")
