import os

import click

from jam import helpers
from jam import velocity


def _get_landable(repo_path):
    """Return (branch, commits) for the most recent branch, or None."""
    result = helpers.run("git fetch --all", cwd=repo_path)
    if result.returncode != 0:
        return None

    result = helpers.run(
        "git for-each-ref --sort=-committerdate refs/remotes/origin/ "
        "--format='%(refname:short)'",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None

    branches = [
        b.strip().strip("'") for b in result.stdout.strip().splitlines()
        if b.strip().strip("'") and b.strip().strip("'") not in ("origin/main", "origin/HEAD")
    ]
    if not branches:
        return None

    branch = branches[0]

    result = helpers.run(
        f"git log origin/main..{branch} --oneline",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None

    commits = result.stdout.strip().splitlines()
    if not commits:
        return None

    return branch, commits


def _compute_velocity_tag(repo_path, branch):
    """Return a string like '[x4.5]' or None if velocity tracking is off or fails."""
    if not helpers.get_jam_config("show_velocity_tag"):
        return None

    baseline = helpers.get_jam_config("baseline_velocity")
    if not baseline or baseline <= 0:
        return None

    result = velocity.branch_velocity(repo_path, "main", branch)
    if result is None:
        return None

    _lines, _hours, vel = result
    if vel <= 0:
        return None

    ratio = vel / baseline
    return f"[x{ratio:.1f}]"


def _ensure_attribution(repo_path):
    """If attribution is enabled but repo lacks .claude/settings.json, add it.

    Returns True on success (or nothing to do), False on failure.
    """
    if not helpers.get_jam_config("attribution_enabled"):
        return True
    if helpers.repo_has_claude_attribution(repo_path):
        return True
    path = helpers.write_repo_claude_settings(repo_path)
    for cmd in [
        "git add .claude/settings.json",
        'git commit -m "add .claude/settings.json for attribution"',
        "git push",
    ]:
        result = helpers.run(cmd, cwd=repo_path)
        if result.returncode != 0:
            click.echo(f"Attribution setup failed: {result.stderr.strip()}")
            return False
    click.echo(f"Added {path}")
    return True


def _do_land(repo_path, branch):
    """Merge branch into main, push, save breadcrumb. Return commit count or None on failure."""
    tag = _compute_velocity_tag(repo_path, branch)

    helpers.run("git checkout main", cwd=repo_path)
    if not _ensure_attribution(repo_path):
        return None

    pre_head = helpers.get_head(repo_path)

    if tag:
        local = branch.replace("origin/", "", 1)
        msg = f"Merge branch '{local}' {tag}"
        result = helpers.run(f"git merge --no-ff {branch} -m \"{msg}\"", cwd=repo_path)
    else:
        result = helpers.run(f"git merge {branch}", cwd=repo_path)
    if result.returncode != 0:
        return None

    result = helpers.run("git push", cwd=repo_path)
    if result.returncode != 0:
        return None

    helpers.save_breadcrumb(repo_path, "land", pre_head=pre_head)
    return True


@click.command()
@click.argument("name", default="")
@click.option("--all", "land_all", is_flag=True, help="Land across all repos.")
def land(name, land_all):
    """Merge the latest branch into main."""
    if land_all:
        _land_all()
    else:
        _land_one(name)


def _land_all():
    jam_home = helpers.get_jam_home()
    targets = []

    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            continue
        info = _get_landable(repo_path)
        if info:
            branch, commits = info
            targets.append((entry, repo_path, branch, commits))

    if not targets:
        click.echo(f"No repos with branches to land {helpers.jam_emoji()}")
        return

    landed = 0
    for repo_name, repo_path, branch, commits in targets:
        n = len(commits)
        local_branch = branch.replace("origin/", "", 1)
        if _do_land(repo_path, branch):
            for c in commits:
                click.echo(f"  {c}")
            click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch} in {repo_name}.")
            landed += 1
        else:
            click.echo(f"Failed to land {local_branch} in {repo_name}.")

    click.echo(f"Landed {landed} repo{'s' if landed != 1 else ''}.")


def _land_one(name):
    repo_path = helpers.resolve_repo(name or None)

    info = _get_landable(repo_path)
    if not info:
        click.echo(f"No branches to land {helpers.jam_emoji()}")
        return

    branch, commits = info
    local_branch = branch.replace("origin/", "", 1)
    n = len(commits)

    if not _do_land(repo_path, branch):
        helpers.fail(f"Failed to land {local_branch}.")

    for c in commits:
        click.echo(f"  {c}")
    click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch}.")
