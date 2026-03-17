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

    # Velocity tagging is optional — only compute tags if a baseline exists
    if baseline and baseline > 0:
        tags = velocity.commit_velocities(repo_path, baseline)
    else:
        tags = {}

    # Count commits eligible for authorship reclaim
    result = helpers.run(
        "git log --all --format=%H:%ae", cwd=repo_path,
    )
    anthropic_shas = [
        line.split(":")[0]
        for line in result.stdout.strip().splitlines()
        if "@anthropic.com" in line
    ]

    if not tags and not anthropic_shas:
        click.echo("Nothing to reclaim.")
        return

    parts = []
    if anthropic_shas:
        parts.append(f"{len(anthropic_shas)} commit(s) to reclaim")
    if tags:
        parts.append(f"{len(tags)} commit(s) to tag")
    click.echo(f"Found {', '.join(parts)} in {os.path.basename(repo_path)}.")
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

        # Write the env-filter to a temp file to avoid shell quoting
        # issues — $GIT_AUTHOR_EMAIL must survive the outer shell and
        # be expanded only when filter-branch evals the script.
        env_filter_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, prefix="jam-reclaim-env-",
        )
        env_filter_file.write(
            f'if echo "$GIT_AUTHOR_EMAIL" | grep -q \'@anthropic.com$\'; then\n'
            f"  export GIT_AUTHOR_NAME='{git_name}'\n"
            f"  export GIT_AUTHOR_EMAIL='{git_email}'\n"
            f"  export GIT_COMMITTER_NAME='{git_name}'\n"
            f"  export GIT_COMMITTER_EMAIL='{git_email}'\n"
            f"fi\n"
        )
        env_filter_file.close()

        # Use forward slashes and single-quote paths so mingw bash
        # on Windows doesn't split on spaces or mangle backslashes.
        python = sys.executable.replace("\\", "/")
        script = script_file.name.replace("\\", "/")
        env_script = env_filter_file.name.replace("\\", "/")
        result = helpers.run(
            f"git filter-branch -f"
            f' --env-filter ". \'{env_script}\'"'
            f" --msg-filter \"'{python}' '{script}'\""
            f" -- --all",
            cwd=repo_path,
        )

        click.echo()  # newline after dots

        if result.returncode != 0:
            click.echo(f"filter-branch failed: {result.stderr.strip()}")
            return

        # Remove backup refs so the original (unrewritten) commits are
        # no longer reachable via refs/original/.
        helpers.run(
            "git for-each-ref --format='delete %(refname)' refs/original/ | "
            "git update-ref --stdin",
            cwd=repo_path,
        )

        helpers.save_breadcrumb(repo_path, "reclaim", pre_head=pre_head)
        parts = []
        if anthropic_shas:
            parts.append(f"Reclaimed {len(anthropic_shas)} commit(s)")
        if tags:
            parts.append(f"tagged {len(tags)} commit(s)")
        click.echo(". ".join(parts) + ".")

    finally:
        os.unlink(map_file.name)
        os.unlink(script_file.name)
        if os.path.exists(counter_file.name):
            os.unlink(counter_file.name)
        if os.path.exists(env_filter_file.name):
            os.unlink(env_filter_file.name)
