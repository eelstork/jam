"""jam reclaim — Retroactively tag commits with velocity markers."""

import json
import os
import sys
import tempfile

import click

from jam import helpers
from jam import velocity


@click.command()
@click.argument("name", default="")
def reclaim(name):
    """Tag existing commits with velocity markers.

    This rewrites commit history. All commit SHAs will change.
    """
    if name:
        repo_path = helpers.resolve_repo(name)
    else:
        repo_path = helpers.git_repo_root()
        if not repo_path:
            helpers.fail("Not in a git repo. Provide a repo name or cd into one.")

    baseline = helpers.get_jam_config("baseline_velocity")
    if not baseline or baseline <= 0:
        helpers.fail(
            "No baseline velocity configured. Run 'jam claim-commits' first."
        )

    # Compute per-commit velocities
    tags = velocity.commit_velocities(repo_path, baseline)
    if not tags:
        click.echo("No commits to tag (too few commits or no measurable velocity).")
        return

    click.echo(f"Found {len(tags)} commit(s) to tag in {os.path.basename(repo_path)}.")
    click.echo()
    click.echo("This will rewrite commit history. All commit SHAs will change.")
    choice = click.prompt(
        "Proceed?",
        type=click.Choice(["yes", "no"], case_sensitive=False),
    )
    if choice == "no":
        click.echo("Aborted.")
        return

    # Write the SHA -> tag mapping to a temp file
    map_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="jam-reclaim-",
    )
    try:
        json.dump(tags, map_file)
        map_file.close()

        # Write the msg-filter script
        script_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="jam-reclaim-",
        )
        script_file.write(f"""\
import json, os, sys
with open({map_file.name!r}) as f:
    tags = json.load(f)
sha = os.environ.get("GIT_COMMIT", "")
msg = sys.stdin.read()
tag = tags.get(sha)
if tag:
    lines = msg.split("\\n", 1)
    first = lines[0].rstrip()
    if not first.endswith("]") or not "[x" in first:
        lines[0] = first + " " + tag
        msg = "\\n".join(lines)
sys.stdout.write(msg)
""")
        script_file.close()

        pre_head = helpers.get_head(repo_path)

        python = sys.executable
        result = helpers.run(
            f'git filter-branch -f --msg-filter "{python} {script_file.name}" -- --all',
            cwd=repo_path,
        )

        if result.returncode != 0:
            click.echo(f"filter-branch failed: {result.stderr.strip()}")
            return

        helpers.save_breadcrumb(repo_path, "reclaim", pre_head=pre_head)
        click.echo(f"Tagged {len(tags)} commit(s).")

    finally:
        os.unlink(map_file.name)
        os.unlink(script_file.name)
