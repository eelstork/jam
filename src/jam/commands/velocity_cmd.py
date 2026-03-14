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

    exclude = "bot,dependabot,renovate"

    classic = velocity.median_velocity(
        repo_path, max_velocity=100,
        exclude_author=exclude, since=since,
    )
    machine = velocity.median_velocity(
        repo_path, max_velocity=10000,
        exclude_author=exclude, since=since,
    )

    if classic is None and machine is None:
        click.echo("Not enough commit data to compute velocity.")
        return

    if classic and classic > 0:
        click.echo(f"Intrinsic velocity: {classic:.1f} l/h")
    else:
        click.echo("Intrinsic velocity: insufficient data")

    if machine and machine > 0:
        click.echo(f"Machine velocity:   {machine:.1f} l/h")
    else:
        click.echo("Machine velocity:   insufficient data")

    if classic and machine and classic > 0:
        accel = machine / classic
        click.echo(f"Accel factor:       x{accel:.1f}")
