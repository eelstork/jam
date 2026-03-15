"""jam stats — Show command usage statistics."""

import os
from collections import Counter

import click

from jam import helpers


@click.command()
@click.option("--clear", is_flag=True, help="Discard the usage log.")
def stats(clear):
    """Show command usage, most used first."""
    log_path = helpers._usage_log_path()

    if clear:
        if os.path.isfile(log_path):
            os.remove(log_path)
            click.echo("Usage log cleared.")
        else:
            click.echo("Nothing to clear.")
        return

    if not os.path.isfile(log_path):
        click.echo("No usage data yet.")
        return

    counts = Counter()
    with open(log_path) as f:
        for line in f:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                counts[parts[1]] += 1

    if not counts:
        click.echo("No usage data yet.")
        return

    for cmd, count in counts.most_common():
        click.echo(f"  {cmd:20s} {count}")
