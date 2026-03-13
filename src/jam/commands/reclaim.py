"""jam reclaim — Reclaim commit authorship and tag with velocity markers."""

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
    """Reclaim commit authorship and tag with velocity markers.

    Rewrites Author/Committer to your git identity and appends
    velocity tags to commit messages. All commit SHAs will change.
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
        counter_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".cnt", delete=False, prefix="jam-reclaim-",
        )
        counter_file.write("0")
        counter_file.close()
        counter_path = counter_file.name.replace("\\", "/")

        click.echo("Rewriting", nl=False)

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
    if not ("[x" in first and first.endswith("]")):
        lines[0] = first + " " + tag
        msg = "\\n".join(lines)
sys.stdout.write(msg)
cf = {counter_path!r}
n = int(open(cf).read()) + 1
open(cf, "w").write(str(n))
if n % 10 == 0:
    sys.stderr.write(".")
    sys.stderr.flush()
""")
        script_file.close()

        pre_head = helpers.get_head(repo_path)

        # Get the user's git identity for authorship reclaim
        git_name = helpers.run("git config user.name", cwd=repo_path).stdout.strip()
        git_email = helpers.run("git config user.email", cwd=repo_path).stdout.strip()
        if not git_name or not git_email:
            helpers.fail("git user.name and user.email must be configured.")

        env_filter = (
            f"export GIT_AUTHOR_NAME='{git_name}';"
            f"export GIT_AUTHOR_EMAIL='{git_email}';"
            f"export GIT_COMMITTER_NAME='{git_name}';"
            f"export GIT_COMMITTER_EMAIL='{git_email}';"
        )

        # Use forward slashes and single-quote paths so mingw bash
        # on Windows doesn't split on spaces or mangle backslashes.
        python = sys.executable.replace("\\", "/")
        script = script_file.name.replace("\\", "/")
        result = helpers.run(
            f"git filter-branch -f"
            f" --env-filter \"{env_filter}\""
            f" --msg-filter \"'{python}' '{script}'\""
            f" -- --all",
            cwd=repo_path,
        )

        click.echo()  # newline after dots

        if result.returncode != 0:
            click.echo(f"filter-branch failed: {result.stderr.strip()}")
            return

        helpers.save_breadcrumb(repo_path, "reclaim", pre_head=pre_head)
        click.echo(f"Tagged {len(tags)} commit(s).")

    finally:
        os.unlink(map_file.name)
        os.unlink(script_file.name)
        if os.path.exists(counter_file.name):
            os.unlink(counter_file.name)
