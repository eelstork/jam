import click


@click.group()
def main():
    """jam - fast and safe git repos"""
    pass


@main.command()
@click.argument("name")
@click.argument("description")
def new(name, description):
    """Create a new repo."""
    click.echo(f"Creating repo: {name}")


@main.command()
@click.argument("source")
@click.argument("target")
@click.argument("description")
def clone(source, target, description):
    """Clone a repo as a new repo."""
    click.echo(f"Cloning {source} as {target}")


@main.command(name="list")
def list_repos():
    """List repos."""
    click.echo("Listing repos")


@main.command()
@click.argument("name")
@click.argument("message")
def up(name, message):
    """Add all, commit, and push."""
    click.echo(f"Pushing {name}: {message}")


@main.command()
def down():
    """Pull latest changes."""
    click.echo("Pulling latest")
