"""Velocity measurement engine, migrated from autofac.

Pure computation — no Click dependency. Uses only stdlib.
"""

import json
import os
import shutil
import stat
import statistics
import subprocess
import tempfile
import urllib.error
import urllib.request


# ── Defaults ────────────────────────────────────────────────────────────

INTRINSIC_MAX_VELOCITY = 100
MACHINE_MAX_VELOCITY = 10000
EXCLUDE_BOTS = "bot,dependabot,renovate"


# ── Git helpers ─────────────────────────────────────────────────────────


def github_get(url, token=None):
    """GET a GitHub API endpoint, following pagination."""
    results = []
    while url:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as resp:
            results.extend(json.loads(resp.read()))
            link = resp.headers.get("Link", "")
            url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip().strip("<>")
    return results


def list_repos(username, token=None):
    """Return list of repos for *username* via the GitHub API."""
    if token:
        url = "https://api.github.com/user/repos?per_page=100&affiliation=owner"
        all_repos = github_get(url, token=token)
        return [r for r in all_repos if r["owner"]["login"].lower() == username.lower()]
    else:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&type=owner"
        return github_get(url, token=None)


def git_in(repo_dir, *args):
    r = subprocess.run(
        ["git", "-C", repo_dir] + list(args),
        capture_output=True, text=True,
    )
    return r.stdout.strip()


def get_commits(repo_dir, author="", exclude_author="", since=""):
    cmd = ["log", "--format=%H %at %aN", "--no-merges"]
    if author:
        cmd += [f"--author={author}"]
    if since:
        cmd += [f"--since={since}"]
    excludes = (
        [e.strip().lower() for e in exclude_author.split(",") if e.strip()]
        if exclude_author else []
    )
    lines = git_in(repo_dir, *cmd).splitlines()
    commits = []
    for line in lines:
        parts = line.split(None, 2)
        if len(parts) >= 2:
            name = parts[2] if len(parts) == 3 else ""
            if excludes and any(ex in name.lower() for ex in excludes):
                continue
            commits.append((parts[0], int(parts[1]), name))
    return commits


def list_authors(repo_dir):
    """Return sorted list of unique author names in the repo."""
    lines = git_in(repo_dir, "log", "--format=%aN", "--no-merges").splitlines()
    return sorted(set(line.strip() for line in lines if line.strip()))


def diff_stat(repo_dir, parent, child):
    lines = git_in(repo_dir, "diff", "--numstat", parent, child).splitlines()
    added = removed = 0
    for line in lines:
        parts = line.split()
        if not parts or parts[0] == "-":
            continue
        added += int(parts[0])
        removed += int(parts[1])
    return added, removed


def clone_repo(clone_url, dest):
    subprocess.run(
        ["git", "clone", "--quiet", clone_url, dest],
        capture_output=True, text=True,
    )


# ── Core velocity computation ───────────────────────────────────────────


def median_velocity(repo_dir, cap_hours=0, max_velocity=0,
                    author="", exclude_author="", gross=False, since=""):
    """Return the median velocity (lines/hour) for *repo_dir*, or None.

    When *gross* is True, uses total lines added (speed) instead of
    net lines (added - removed).
    """
    commits = get_commits(repo_dir, author=author, exclude_author=exclude_author,
                          since=since)
    if len(commits) < 2:
        return None

    cap_sec = cap_hours * 3600 if cap_hours > 0 else 0
    velocities = []
    for i in range(len(commits) - 1):
        sha, ts, _name = commits[i]
        prev_sha, prev_ts, _prev_name = commits[i + 1]

        added, removed = diff_stat(repo_dir, prev_sha, sha)
        delta = added if gross else added - removed

        gap_sec = ts - prev_ts
        if gap_sec <= 0:
            interval = 0
        elif cap_sec > 0:
            interval = min(gap_sec, cap_sec)
        else:
            interval = gap_sec
        capped_hours = interval / 3600

        if interval > 0:
            vel = delta / capped_hours
            if max_velocity > 0 and vel > max_velocity:
                continue
            velocities.append(vel)

    if not velocities:
        return None
    return statistics.median(velocities)


# ── Aggregate velocity (scan all repos) ─────────────────────────────────


def _force_remove_readonly(func, path, _exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def force_rmtree(path):
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=_force_remove_readonly)


def resolve_github_credentials():
    """Return (username, token) using gh CLI and env vars."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        try:
            r = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                token = r.stdout.strip()
        except FileNotFoundError:
            pass

    username = ""
    try:
        r = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            username = r.stdout.strip()
    except FileNotFoundError:
        pass

    return username, token


def aggregate_velocity(username, token, max_size_mb=25, cap_hours=0,
                       max_velocity=100, exclude_author="",
                       on_progress=None):
    """Scan all repos for *username*, return averaged median velocity or None.

    *on_progress(event, **kw)* is called with status updates.
    """
    repos = list_repos(username, token=token or None)
    if not repos:
        return None

    if on_progress:
        on_progress("repo_count", count=len(repos))

    workdir = tempfile.mkdtemp(prefix="jam-velocity-")
    medians = []
    try:
        for repo in sorted(repos, key=lambda r: r["name"]):
            name = repo["name"]
            size_kb = repo.get("size", 0)
            is_fork = repo.get("fork", False)

            if is_fork:
                continue

            max_size_kb = max_size_mb * 1024
            if max_size_mb and size_kb > max_size_kb:
                if on_progress:
                    on_progress("repo_skip", name=name, reason="too large")
                continue

            dest = os.path.join(workdir, name)
            if on_progress:
                on_progress("repo_clone", name=name, size_kb=size_kb)
            clone_repo(repo["clone_url"], dest)

            med = median_velocity(
                dest, cap_hours=cap_hours, max_velocity=max_velocity,
                exclude_author=exclude_author,
            )

            if med is not None and med > 0:
                medians.append((name, med))
                if on_progress:
                    on_progress("repo_velocity", name=name, velocity=med)
            else:
                if on_progress:
                    on_progress("repo_empty", name=name)

            force_rmtree(dest)
    finally:
        force_rmtree(workdir)

    if not medians:
        return None
    values = [v for _, v in medians]
    return statistics.mean(values)


# ── Branch velocity (for jam land) ──────────────────────────────────────


def branch_velocity(repo_dir, base_ref, head_ref, gross=False):
    """Compute velocity for a branch's commits.

    When *gross* is True, uses total lines added (speed).
    Default uses net lines (added - removed) for consistency with
    median_velocity and commit_velocities.

    Returns (lines_changed, elapsed_hours, velocity_lph) or None.
    """
    # Get commits on the branch since the merge base
    merge_base = git_in(repo_dir, "merge-base", base_ref, head_ref)
    if not merge_base:
        return None

    lines = git_in(
        repo_dir, "log", "--format=%H %at", "--no-merges",
        f"{merge_base}..{head_ref}",
    ).splitlines()

    if not lines:
        return None

    timestamps = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            timestamps.append(int(parts[1]))

    if not timestamps:
        return None

    # Total lines changed on the branch
    added, removed = diff_stat(repo_dir, merge_base, head_ref)
    delta = added if gross else added - removed

    if delta <= 0:
        return None

    # Time window: earliest to latest commit on the branch
    earliest = min(timestamps)
    latest = max(timestamps)
    elapsed_sec = latest - earliest
    if elapsed_sec <= 0:
        return None

    elapsed_hours = elapsed_sec / 3600
    vel = delta / elapsed_hours

    return delta, elapsed_hours, vel


# ── Per-commit velocity (for jam reclaim) ───────────────────────────────


def commit_velocities(repo_dir, baseline, gross=False):
    """Return a dict mapping commit SHA to velocity tag string.

    For each consecutive pair of commits, computes velocity and the ratio
    against *baseline*. Commits where velocity can't be computed are omitted.

    When *gross* is True, uses total lines added (speed) instead of
    net lines (added - removed).
    """
    commits = get_commits(repo_dir)
    if len(commits) < 2:
        return {}

    tags = {}
    for i in range(len(commits) - 1):
        sha, ts, _name = commits[i]
        prev_sha, prev_ts, _prev_name = commits[i + 1]

        added, removed = diff_stat(repo_dir, prev_sha, sha)
        delta = added if gross else added - removed

        gap_sec = ts - prev_ts
        if gap_sec <= 0 or delta <= 0:
            continue

        hours = gap_sec / 3600
        vel = delta / hours
        ratio = vel / baseline
        if ratio > 0:
            tags[sha] = f"[x{ratio:.1f}]"

    return tags
