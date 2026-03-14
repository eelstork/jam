"""jam velocity — Evaluate velocity for a repo."""

import sys

import click

from jam import helpers
from jam import velocity


PERIODS = [
    ("week",  "Past week",   "1.week.ago"),
    ("month", "Past month",  "1.month.ago"),
    ("all",   "All time",    ""),
]


@click.command("velocity")
@click.argument("name", default="")
def velocity_cmd(name):
    """Evaluate velocity for a repo."""
    repo_path = helpers.resolve_repo(name or None)

    # Let the user pick a time period
    if sys.stdin.isatty():
        from jam.interactive import pick

        items = [(label, desc) for label, desc, _ in PERIODS]
        idx = pick(items, header="Time period")
        if idx is None:
            return
    else:
        idx = 2  # default to all time in non-interactive mode

    label, desc, since = PERIODS[idx]
    click.echo(f"Measuring velocity ({desc.lower()}) ...")

    med = velocity.median_velocity(repo_path, since=since)

    if med is None:
        click.echo("Not enough commit data to compute velocity.")
        return

    click.echo(f"Median velocity: {med:.1f} lines/hour")
