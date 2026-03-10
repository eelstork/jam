import click

from jam.commands.clone import clone
from jam.commands.delete import delete
from jam.commands.down import down
from jam.commands.infuse import infuse
from jam.commands.land import land
from jam.commands.list import list_repos
from jam.commands.new import new
from jam.commands.undo import undo
from jam.commands.up import up


@click.group()
def main():
    """jam - fast and safe git repos"""
    pass


main.add_command(new)
main.add_command(clone)
main.add_command(list_repos)
main.add_command(up)
main.add_command(down)
main.add_command(land)
main.add_command(infuse)
main.add_command(undo)
main.add_command(delete)
