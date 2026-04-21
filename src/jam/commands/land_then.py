"""`jam l<CMD> REPO [ARGS...]` — land, then run CMD as a passthrough.

Shortcut for the common land-then-deploy flow. Runs land in-process; if
there's nothing to land, skips CMD and exits cleanly. If land fails, the
failure propagates. Otherwise CMD runs with the same repo and any extra
args forwarded.
"""

import click

from jam import helpers
from jam.commands.land import _land_one
from jam.commands.run_script import make_command


def make_land_then_command(inner_name):
    """Return a Click command for `jam l<inner_name>`."""
    full_name = "l" + inner_name

    @click.command(
        full_name,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    def cmd(args):
        args = list(args)
        if not args:
            helpers.fail(f"Usage: jam {full_name} REPO [ARGS...]")

        repo = args[0]
        status = _land_one(repo)
        if status == "nothing":
            return

        passthrough = make_command(inner_name)
        ctx = click.get_current_context()
        ctx.invoke(passthrough, args=tuple(args))

    cmd.help = f"Land, then run {inner_name} (shortcut for land + {inner_name})"
    return cmd
