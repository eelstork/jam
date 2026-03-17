"""jam tag-velocity — Enable or disable velocity tagging."""

import click

from jam import helpers


@click.command("tag-velocity")
@click.argument("action", type=click.Choice(["enable", "disable"], case_sensitive=False))
def tag_velocity(action):
    """Enable or disable velocity tagging on commits."""
    if action == "enable":
        baseline = helpers.get_jam_config("baseline_velocity")
        if not baseline or baseline <= 0:
            click.echo(
                "Velocity tagging requires a baseline velocity, but none has been set.\n"
                "Run `jam velocity` to measure your coding velocity, then add\n"
                "\"baseline_velocity\": <value> to your jam config (~/.config/jam/config.json)."
            )
            raise SystemExit(1)
        helpers.save_jam_config(show_velocity_tag=True)
        click.echo("Velocity tagging enabled.")
    else:
        helpers.save_jam_config(show_velocity_tag=False)
        click.echo("Velocity tagging disabled.")
