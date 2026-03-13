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
        "--format=%(refname:short)",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None

    branches = [
        b.strip() for b in result.stdout.strip().splitlines()
        if b.strip() and b.strip() not in ("origin/main", "origin/HEAD")
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
    """If attribution is enabled but repo lacks .claude/settings.json, add it."""
    if not helpers.get_jam_config("attribution_enabled"):
        return
    if helpers.repo_has_claude_attribution(repo_path):
        return
    path = helpers.write_repo_claude_settings(repo_path)
    helpers.run("git add .claude/settings.json", cwd=repo_path)
    helpers.run('git commit -m "add .claude/settings.json for attribution"', cwd=repo_path)
    helpers.run("git push", cwd=repo_path)
    click.echo(f"Added {path}")


def _do_land(repo_path, branch):
    """Merge branch into main, push, save breadcrumb. Return commit count or None on failure."""
    tag = _compute_velocity_tag(repo_path, branch)

    helpers.run("git checkout main", cwd=repo_path)
    _ensure_attribution(repo_path)

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
@click.option("--fast", is_flag=True, help="Land without confirmation.")
def land(name, land_all, fast):
    """Merge the latest branch into main."""
    if land_all:
        _land_all(fast)
    else:
        _land_one(name, fast)


def _land_all(fast):
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

    if not fast:
        for repo_name, _, branch, commits in targets:
            last = commits[0]
            n = len(commits)
            suffix = f" (+{n})" if n > 1 else ""
            click.echo(f"  {repo_name} -- {last}{suffix}")
        click.echo()
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    landed = 0
    for repo_name, repo_path, branch, commits in targets:
        n = len(commits)
        local_branch = branch.replace("origin/", "", 1)
        if _do_land(repo_path, branch):
            click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch} in {repo_name}.")
            landed += 1
        else:
            click.echo(f"Failed to land {local_branch} in {repo_name}.")

    click.echo(f"Landed {landed} repo{'s' if landed != 1 else ''}.")


def _land_one(name, fast):
    repo_path = helpers.resolve_repo(name or None)

    info = _get_landable(repo_path)
    if not info:
        click.echo(f"No branches to land {helpers.jam_emoji()}")
        return

    branch, commits = info
    local_branch = branch.replace("origin/", "", 1)
    n = len(commits)

    if not fast:
        click.echo(f"Landing {branch} ({n} commit{'s' if n != 1 else ''}):")
        click.echo()
        display = commits[:3]
        for c in display:
            click.echo(f"  {c}")
        if n > 3:
            click.echo(f"  ... and {n - 3} more")
        click.echo()
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    if not _do_land(repo_path, branch):
        helpers.fail(f"Failed to land {local_branch}.")

    click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch}.")
