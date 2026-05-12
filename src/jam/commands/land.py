import json
import os

import click

from jam import helpers
from jam import velocity


def _find_open_pr(repo_path):
    """Return (pr_number, head_branch, title) for the most recently updated
    open PR, or None if there is no open PR / no GitHub remote / gh is
    unavailable.
    """
    result = helpers.run(
        "gh pr list --state open --json number,headRefName,title,updatedAt "
        "--limit 100",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None
    try:
        prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not prs:
        return None
    prs.sort(key=lambda p: p.get("updatedAt", ""), reverse=True)
    pr = prs[0]
    num = pr.get("number")
    head = pr.get("headRefName")
    if num is None or not head:
        return None
    return num, head, pr.get("title") or ""


def _commits_on(repo_path, branch):
    """Return ([commits], None) on success, (None, error_str) on failure."""
    result = helpers.run(
        f"git log origin/main..{branch} --oneline",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None, f"could not read commits: {result.stderr.strip()}"
    return result.stdout.strip().splitlines(), None


def _latest_branch(repo_path):
    """Return (branch, None) for the most recent non-main remote branch,
    (None, None) if there is none, or (None, error_str) on failure.
    """
    result = helpers.run(
        "git for-each-ref --sort=-committerdate refs/remotes/origin/ "
        "--format='%(refname:short)'",
        cwd=repo_path,
    )
    if result.returncode != 0:
        return None, f"could not list branches: {result.stderr.strip()}"

    branches = [
        b.strip().strip("'") for b in result.stdout.strip().splitlines()
        if b.strip().strip("'") and b.strip().strip("'") not in ("origin/main", "origin/HEAD")
    ]
    if not branches:
        return None, None
    return branches[0], None


def _get_landable(repo_path):
    """Pick something to land, preferring any open PR over the latest branch.

    Returns one of:
      - error string
      - None when there's nothing to land
      - (branch, commits, pr_number, pr_title) where pr_number and pr_title
        are both None for the branch-only fallback.
    """
    result = helpers.run("git fetch --all", cwd=repo_path)
    if result.returncode != 0:
        return f"fetch failed: {result.stderr.strip()}"

    pr = _find_open_pr(repo_path)
    if pr is not None:
        pr_number, head, title = pr
        branch = f"origin/{head}"
        commits, error = _commits_on(repo_path, branch)
        if error is not None:
            return error
        if not commits:
            return None
        return branch, commits, pr_number, title

    branch, error = _latest_branch(repo_path)
    if error is not None:
        return error
    if branch is None:
        return None

    commits, error = _commits_on(repo_path, branch)
    if error is not None:
        return error
    if not commits:
        return None
    return branch, commits, None, None


def _do_land_pr(repo_path, branch, pr_number):
    """Merge an open PR via gh, sync local main, save breadcrumb.

    Returns True on success, or an error string on failure.
    """
    tag = _compute_velocity_tag(repo_path, branch)

    result = helpers.run("git checkout main", cwd=repo_path)
    if result.returncode != 0:
        return f"checkout main failed: {result.stderr.strip()}"

    if not _ensure_attribution(repo_path):
        return "attribution setup failed"

    pre_head = helpers.get_head(repo_path)

    cmd = f"gh pr merge {pr_number} --merge"
    if tag:
        local = branch.replace("origin/", "", 1)
        subject = f"Merge pull request #{pr_number} from {local} {tag}"
        cmd += f" --subject \"{subject}\""
    result = helpers.run(cmd, cwd=repo_path)
    if result.returncode != 0:
        return f"PR merge failed: {result.stderr.strip()}"

    result = helpers.run("git pull", cwd=repo_path)
    if result.returncode != 0:
        return f"sync failed: {result.stderr.strip()}"

    helpers.save_breadcrumb(repo_path, "land", pre_head=pre_head)
    return True


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
    """If attribution is enabled but repo lacks complete settings, add them.

    Returns True on success (or nothing to do), False on failure.
    """
    pre_head = helpers.get_head(repo_path)
    if not helpers.ensure_repo_claude_settings(repo_path):
        click.echo("Attribution setup failed.")
        return False
    # Push if ensure_repo_claude_settings made a commit
    if helpers.get_head(repo_path) != pre_head:
        push = helpers.run("git push", cwd=repo_path)
        if push.returncode != 0:
            click.echo(f"Attribution push failed: {push.stderr.strip()}")
            return False
    return True


def _do_land(repo_path, branch):
    """Merge branch into main, push, save breadcrumb.

    Returns True on success, or an error string on failure.
    """
    tag = _compute_velocity_tag(repo_path, branch)

    result = helpers.run("git checkout main", cwd=repo_path)
    if result.returncode != 0:
        return f"checkout main failed: {result.stderr.strip()}"

    if not _ensure_attribution(repo_path):
        return "attribution setup failed"

    pre_head = helpers.get_head(repo_path)

    if tag:
        local = branch.replace("origin/", "", 1)
        msg = f"Merge branch '{local}' {tag}"
        result = helpers.run(f"git merge --no-ff {branch} -m \"{msg}\"", cwd=repo_path)
    else:
        result = helpers.run(f"git merge {branch}", cwd=repo_path)
    if result.returncode != 0:
        return f"merge failed: {result.stderr.strip()}"

    result = helpers.run("git push", cwd=repo_path)
    if result.returncode != 0:
        return f"push failed: {result.stderr.strip()}"

    helpers.save_breadcrumb(repo_path, "land", pre_head=pre_head)
    return True


@click.command()
@click.argument("names", nargs=-1)
@click.option("--all", "land_all", is_flag=True, help="Land across all repos.")
def land(names, land_all):
    """Merge the latest open PR (or branch) into main."""
    if land_all:
        _land_all()
    else:
        # Flatten comma-separated entries: "a, b" "c" -> ["a", "b", "c"]
        repos = []
        for n in names:
            for part in n.split(","):
                part = part.strip()
                if part:
                    repos.append(part)
        if not repos:
            repos = [""]
        for repo in repos:
            _land_one(repo)


def _land_all():
    jam_home = helpers.get_jam_home()
    targets = []
    errors = []

    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            continue
        click.echo(".", nl=False)
        info = _get_landable(repo_path)
        if isinstance(info, str):
            errors.append((entry, info))
        elif info is not None:
            branch, commits, pr_number, pr_title = info
            targets.append((entry, repo_path, branch, commits, pr_number, pr_title))

    click.echo()  # newline after dots

    if not targets and not errors:
        click.echo(f"No repos with branches to land {helpers.jam_emoji()}")
        return

    landed = []
    failed = []
    for repo_name, repo_path, branch, commits, pr_number, pr_title in targets:
        local_branch = branch.replace("origin/", "", 1)
        click.echo(".", nl=False)
        if pr_number is not None:
            result = _do_land_pr(repo_path, branch, pr_number)
        else:
            result = _do_land(repo_path, branch)
        if result is True:
            landed.append((repo_name, local_branch, commits, pr_number, pr_title))
        else:
            failed.append((repo_name, local_branch, result))

    click.echo()  # newline after dots

    for repo_name, local_branch, commits, pr_number, pr_title in landed:
        for c in commits:
            click.echo(f"  {c}")
        n = len(commits)
        click.echo(_landed_line(local_branch, n, pr_number, pr_title, repo_name=repo_name))

    for repo_name, local_branch, reason in failed:
        click.echo(f"Failed to land {local_branch} in {repo_name}: {reason}")

    for repo_name, reason in errors:
        click.echo(f"Skipped {repo_name}: {reason}")

    click.echo(f"Landed {len(landed)} repo{'s' if len(landed) != 1 else ''}.")


def _land_one(name):
    """Land the latest open PR (or branch) in the repo named *name* (or cwd if falsy).

    Returns "landed" on success, "nothing" when there's nothing to land.
    Errors abort the process via helpers.fail.
    """
    repo_path = helpers.resolve_repo(name or None)

    info = _get_landable(repo_path)
    if isinstance(info, str):
        helpers.fail(info)
    if info is None:
        click.echo(f"No branches to land {helpers.jam_emoji()}")
        return "nothing"

    branch, commits, pr_number, pr_title = info
    local_branch = branch.replace("origin/", "", 1)
    n = len(commits)

    if pr_number is not None:
        result = _do_land_pr(repo_path, branch, pr_number)
    else:
        result = _do_land(repo_path, branch)
    if result is not True:
        helpers.fail(f"Failed to land {local_branch}: {result}")

    for c in commits:
        click.echo(f"  {c}")
    click.echo(_landed_line(local_branch, n, pr_number, pr_title))
    return "landed"


def _landed_line(local_branch, n, pr_number, pr_title, repo_name=None):
    """Format the final 'Landed ...' summary line.

    When a PR was landed, lead with the PR (number + title) so the user
    gets human-readable feedback. Otherwise keep the historical wording.
    """
    plural = "s" if n != 1 else ""
    where = f" in {repo_name}" if repo_name else ""
    if pr_number is not None:
        title = (pr_title or "").strip()
        title_part = f": {title}" if title else ""
        return (
            f"Landed PR #{pr_number}{title_part} "
            f"({n} commit{plural} from {local_branch}{where})."
        )
    return f"Landed {n} commit{plural} from {local_branch}{where}."
