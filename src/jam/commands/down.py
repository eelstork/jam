import click

from jam import helpers


@click.command()
@click.argument("name", default="")
@click.option("--force", is_flag=True, help="Force pull (discard local changes).")
@click.pass_context
def down(ctx, name, force):
    """Pull latest changes, or clone from remote if not local."""
    if name and not helpers.is_repo(name):
        from jam.commands.clone import clone

        ctx.invoke(clone, name=name)
        return

    repo_path = helpers.resolve_repo(name or None)

    pre_head = helpers.get_head(repo_path)

    if force:
        helpers.run("git reset --hard HEAD", cwd=repo_path)

    result = helpers.run("git pull", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git pull failed: {result.stderr.strip()}")

    helpers.save_breadcrumb(repo_path, "down", pre_head=pre_head)
    click.echo("Pulled.")
