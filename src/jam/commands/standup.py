"""jam standup — Show yesterday's commits across all repos."""

from datetime import datetime, timedelta

import click

from jam.commands._log_since import log_since


@click.command()
def standup():
    """List commits since 7 am yesterday per repo."""
    since = (datetime.now() - timedelta(days=1)).replace(hour=7, minute=0, second=0)
    log_since(since, "No commits since 7 am yesterday.")
