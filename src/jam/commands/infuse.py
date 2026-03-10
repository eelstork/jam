import os
import shutil

import click

from jam import helpers


@click.command()
@click.argument("source")
@click.option("--into", "target", default="", help="Target repo or repo/path.")
def infuse(source, target):
    """Copy files from one repo into another."""
    jam_home = helpers.get_jam_home()

    src_path = os.path.join(jam_home, source)
    if not os.path.isdir(src_path):
        helpers.fail(f"Repo {source} not found at {src_path}")

    dest_subpath = None

    if target:
        parts = target.split("/", 1)
        target_name = parts[0]
        target_path = os.path.join(jam_home, target_name)
        if not os.path.isdir(target_path):
            helpers.fail(f"Repo {target_name} not found at {target_path}")
        if len(parts) == 2:
            dest_subpath = parts[1]
            full_dest = os.path.join(target_path, dest_subpath)
            if os.path.exists(full_dest):
                helpers.fail(f"Path {target} already exists.")
            target_path = full_dest
    else:
        target_path = helpers.resolve_repo(None)
        target_name = os.path.basename(target_path)

    conflicts = []
    to_copy = []
    for dirpath, dirnames, filenames in os.walk(src_path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fname in filenames:
            src_file = os.path.join(dirpath, fname)
            rel = os.path.relpath(src_file, src_path)
            dst_file = os.path.join(target_path, rel)
            if os.path.exists(dst_file):
                conflicts.append(rel)
            else:
                to_copy.append((src_file, dst_file))

    if conflicts:
        click.echo("Conflict \u2014 these files already exist in target:")
        for c in conflicts:
            click.echo(f"  {c}")
        dest_label = f"{target_name}/{dest_subpath}" if dest_subpath else target_name
        helpers.fail(f"Cannot infuse {source} into {dest_label} (conflicts).")

    if not to_copy:
        click.echo("Nothing to infuse.")
        return

    for src_file, dst_file in to_copy:
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.copy2(src_file, dst_file)

    dest_label = f"{target_name}/{dest_subpath}" if dest_subpath else target_name

    # Resolve the git root for the target repo (not the subpath)
    if target:
        parts = target.split("/", 1)
        git_root = os.path.join(jam_home, parts[0])
    else:
        git_root = target_path

    pre_head = helpers.get_head(git_root)

    helpers.run("git add -A", cwd=git_root)
    helpers.run(f'git commit -m "infuse {source}"', cwd=git_root)

    helpers.save_breadcrumb(git_root, "infuse", pre_head=pre_head)

    count = len(to_copy)
    click.echo(f"Infused {count} file{'s' if count != 1 else ''} from {source} into {dest_label}.")
