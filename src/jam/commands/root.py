import click

from jam import helpers


@click.command()
def root():
    """Show the current jam root directory."""
    click.echo(helpers.get_jam_home())
