"""jam retro — Show the past week's commits across all repos."""

from datetime import datetime, timedelta

import click

from jam.commands._log_since import log_since


@click.command()
def retro():
    """List commits from the past week per repo."""
    today = datetime.now()
    # Go back 7 days, then rewind to Monday.
    week_ago = today - timedelta(days=7)
    last_monday = week_ago - timedelta(days=week_ago.weekday())
    since = last_monday.replace(hour=7, minute=0, second=0)
    log_since(since, "No commits in the past week.")
