"""jam cooldown — Show today's commits across all repos."""

from datetime import datetime

import click

from jam.commands._log_since import log_since


@click.command()
def cooldown():
    """List today's commits (since 7 am) per repo."""
    since = datetime.now().replace(hour=7, minute=0, second=0)
    log_since(since, "No commits since 7 am today.")
