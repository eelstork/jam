import click

from jam import helpers


@click.command()
@click.argument("name", default="")
@click.option("--force", is_flag=True, help="Force pull (discard local changes).")
def down(name, force):
    """Pull latest changes."""
    repo_path = helpers.resolve_repo(name or None)

    if force:
        helpers.run("git reset --hard HEAD", cwd=repo_path)

    result = helpers.run("git pull", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git pull failed: {result.stderr.strip()}")

    click.echo("Pulled.")
