import os

import click

from jam import helpers


@click.command(name="list")
@click.option("--info", is_flag=True, help="Show description from README.")
def list_repos(info):
    """List repos."""
    jam_home = helpers.get_jam_home()
    for entry in sorted(os.listdir(jam_home)):
        path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        if not info:
            click.echo(entry)
            continue
        readme_path = os.path.join(path, "README.md")
        desc = ""
        if os.path.isfile(readme_path):
            with open(readme_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        desc = line
                        break
        if desc:
            click.echo(f"{entry} \u2014 {desc}")
        else:
            click.echo(entry)
