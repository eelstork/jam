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
@click.option("--commits", "-c", "max_commits", type=int, default=0,
              help="Only look back at most N commits.")
def reclaim(name, max_commits):
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

    # Ensure .claude/settings.json is up to date (commits if needed)
    if not helpers.ensure_repo_claude_settings(repo_path):
        helpers.fail("Failed to update .claude/settings.json.")

    # Ensure the working tree is clean before rewriting history
    status = helpers.run("git status --porcelain", cwd=repo_path)
    if status.stdout.strip():
        helpers.fail("Working tree is not clean. Commit or stash changes first.")

    # Detect current branch and its upstream for force push
    branch_result = helpers.run(
        "git rev-parse --abbrev-ref HEAD", cwd=repo_path,
    )
    branch = branch_result.stdout.strip()
    if not branch or branch == "HEAD":
        helpers.fail("Not on a branch. Check out a branch first.")

    upstream_result = helpers.run(
        f"git rev-parse --abbrev-ref {branch}@{{upstream}}", cwd=repo_path,
    )
    has_upstream = upstream_result.returncode == 0

    # Clean up any stale refs/original/ from a previous run — these are
    # backup refs created by git filter-branch that cause git log
    # to see old (unrewritten) commits, making reclaim non-idempotent.
    helpers.run(
        "git for-each-ref --format='delete %(refname)' refs/original/ | "
        "git update-ref --stdin",
        cwd=repo_path,
    )

    baseline = helpers.get_jam_config("baseline_velocity")

    # Velocity tagging is optional — requires both a baseline and the toggle
    if baseline and baseline > 0 and helpers.get_jam_config("show_velocity_tag"):
        tags = velocity.commit_velocities(repo_path, baseline,
                                          max_count=max_commits)
    else:
        tags = {}

    # Count commits eligible for authorship reclaim (current branch only)
    # Also grab subjects to skip already-tagged commits
    log_cmd = "git log --format=%H:%ae:%s"
    if max_commits > 0:
        log_cmd += f" --max-count={max_commits}"
    result = helpers.run(log_cmd, cwd=repo_path)
    anthropic_shas = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 2)
        sha, email, subject = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
        if "@anthropic.com" in email:
            anthropic_shas.append(sha)
        # Skip velocity tagging for commits that already have a tag
        if sha in tags and "[x" in subject and subject.rstrip().endswith("]"):
            del tags[sha]

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
    click.echo(
        "This will rewrite commit history and requires a force push"
        f" on the current branch ({branch}). Commit SHAs may change."
    )
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
        if max_commits > 0:
            rev_range = f"HEAD~{max_commits}..HEAD"
        else:
            rev_range = branch
        result = helpers.run(
            f"git filter-branch -f"
            f' --env-filter ". \'{env_script}\'"'
            f" --msg-filter \"'{python}' '{script}'\""
            f" -- {rev_range}",
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

        # Force push the rewritten branch
        if has_upstream:
            click.echo(f"Force pushing {branch}...")
            push_result = helpers.run(
                f"git push --force-with-lease origin {branch}",
                cwd=repo_path,
            )
            if push_result.returncode != 0:
                click.echo(f"Push failed: {push_result.stderr.strip()}")
            else:
                click.echo("Pushed.")
        else:
            click.echo(
                f"Branch {branch} has no upstream. Push manually when ready."
            )

    finally:
        os.unlink(map_file.name)
        os.unlink(script_file.name)
        if os.path.exists(counter_file.name):
            os.unlink(counter_file.name)
        if os.path.exists(env_filter_file.name):
            os.unlink(env_filter_file.name)
