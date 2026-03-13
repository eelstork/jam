import sys

import click

from jam import helpers
from jam.commands.clone import clone
from jam.commands.delete import delete
from jam.commands.down import down
from jam.commands.infuse import infuse
from jam.commands.land import land
from jam.commands.list import list_repos
from jam.commands.new import new
from jam.commands.root import root
from jam.commands.set_root import set_root
from jam.commands.undo import undo
from jam.commands.up import up
from jam.commands.update import update
from jam.commands.claim_commits import claim_commits
from jam.commands.reclaim import reclaim


COMMANDS = [
    ("new",    "Create a new repo",               new),
    ("clone",  "Clone a repo as a new repo",       clone),
    ("list",   "List repos",                       list_repos),
    ("up",     "Add all, commit, and push",        up),
    ("down",   "Pull latest changes",              down),
    ("land",   "Merge the latest branch into main", land),
    ("infuse", "Copy files from one repo into another", infuse),
    ("undo",   "Undo the last jam command",        undo),
    ("delete", "Delete a repo locally",            delete),
    ("root",   "Show the jam root directory",      root),
    ("set-root", "Set the jam root directory",     set_root),
    ("update",   "Update jam to the latest version", update),
    ("claim-commits", "Set up commit attribution and velocity", claim_commits),
    ("reclaim", "Tag existing commits with velocity markers", reclaim),
]


class _JamGroup(click.Group):
    """Click group that falls back to repo-root scripts."""

    def get_command(self, ctx, cmd_name):
        # Built-in commands take priority.
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd

        # Defer script resolution to the command itself — we don't know
        # yet whether the user is targeting a named repo or the cwd.
        from jam.commands.run_script import make_command

        return make_command(cmd_name)


@click.group(cls=_JamGroup, invoke_without_command=True)
@click.pass_context
def main(ctx):
    """jam - fast and safe git repos"""
    if ctx.invoked_subcommand is None:
        _interactive()


def _interactive():
    """Walk the user through commands interactively."""
    if not sys.stdin.isatty():
        click.echo(click.get_current_context().get_help())
        return

    if not helpers.get_jam_config("claim_commits_done"):
        click.echo("Tip: run 'jam claim-commits' to set up commit attribution.\n")

    from jam.interactive import pick

    items = [(name, desc) for name, desc, _ in COMMANDS]
    idx = pick(items, header="jam")
    if idx is None:
        return

    name, _, cmd = COMMANDS[idx]
    click.echo(f"jam {name}")

    # Collect required arguments interactively before invoking.
    kwargs = {}
    for param in cmd.params:
        if isinstance(param, click.Argument) and param.required:
            kwargs[param.name] = click.prompt(param.name.replace("_", " ").capitalize())
        elif isinstance(param, click.Option) and param.is_flag:
            # skip flags — use defaults
            pass

    ctx = click.get_current_context()
    ctx.invoke(cmd, **kwargs)


main.add_command(new)
main.add_command(new, "create")
main.add_command(clone)
main.add_command(list_repos)
main.add_command(up)
main.add_command(down)
main.add_command(land)
main.add_command(infuse)
main.add_command(undo)
main.add_command(delete)
main.add_command(root)
main.add_command(set_root)
main.add_command(update)
main.add_command(claim_commits)
main.add_command(reclaim)
