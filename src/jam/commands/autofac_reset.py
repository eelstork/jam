"""jam autofac-reset — Clear velocity and attribution config for re-testing."""

import os
import shutil

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

    repo_root = helpers.git_repo_root()
    if repo_root:
        claude_dir = os.path.join(repo_root, ".claude")
        if os.path.isdir(claude_dir):
            shutil.rmtree(claude_dir)
            click.echo(f"Removed {claude_dir}")

    click.echo("Reset. Run 'jam claim-commits' to set up again.")
