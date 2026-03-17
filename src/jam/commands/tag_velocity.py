"""jam tag-velocity — Enable or disable velocity tagging."""

import click

from jam import helpers


@click.command("tag-velocity")
@click.argument("action", type=click.Choice(["enable", "disable"], case_sensitive=False))
def tag_velocity(action):
    """Enable or disable velocity tagging on commits."""
    if action == "enable":
        helpers.save_jam_config(show_velocity_tag=True)
        click.echo("Velocity tagging enabled.")
    else:
        helpers.save_jam_config(show_velocity_tag=False)
        click.echo("Velocity tagging disabled.")
