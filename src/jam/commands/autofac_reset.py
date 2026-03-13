"""jam autofac-reset — Clear velocity and attribution config for re-testing."""

import click

from jam import helpers


@click.command("autofac-reset")
def autofac_reset():
    """Clear velocity and attribution config.

    Resets claim-commits state so the workflow can be re-run.
    """
    helpers.save_jam_config(
        claim_commits_done=False,
        attribution_enabled=False,
        baseline_velocity=None,
        machine_velocity=None,
        multiplier=None,
        show_velocity_tag=False,
    )
    click.echo("Reset. Run 'jam claim-commits' to set up again.")
