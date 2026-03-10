import click

from jam import helpers


@click.command()
@click.argument("message")
@click.option("--name", "-n", default="", help="Repo name (default: current dir).")
@click.option("--force", is_flag=True, help="Force push.")
def up(message, name, force):
    """Add all, commit, and push."""
    repo_path = helpers.resolve_repo(name or None)

    pre_head = helpers.get_head(repo_path)

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
