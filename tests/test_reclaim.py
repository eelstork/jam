"""Tests for jam reclaim idempotency."""

import os
import subprocess
import tempfile

from click.testing import CliRunner

from jam.cli import main
from jam import helpers


def _git(repo, *args, **kwargs):
    return subprocess.run(
        ["git", "-C", repo] + list(args),
        capture_output=True, text=True, **kwargs,
    )


def _make_repo_with_anthropic_commits():
    """Create a temp repo with commits from @anthropic.com."""
    d = tempfile.mkdtemp(prefix="jam-test-reclaim-")
    _git(d, "init")
    _git(d, "config", "user.name", "Test User")
    _git(d, "config", "user.email", "test@example.com")
    _git(d, "config", "commit.gpgsign", "false")

    # Initial commit from the user
    with open(os.path.join(d, "readme.txt"), "w") as f:
        f.write("hello\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-m", "initial commit")

    # Anthropic-authored commits
    for i in range(3):
        with open(os.path.join(d, f"file{i}.txt"), "w") as f:
            f.write(f"content {i}\n")
        _git(d, "add", "-A")
        _git(
            d,
            "-c", "user.name=Claude",
            "-c", "user.email=claude@anthropic.com",
            "commit", "-m", f"ai commit {i}",
        )

    return d


def test_reclaim_idempotent():
    """Running reclaim twice: second run should be a no-op."""
    repo = _make_repo_with_anthropic_commits()
    runner = CliRunner()

    # First run — should reclaim the anthropic commits
    result = runner.invoke(main, ["reclaim"], input="yes\n", env={
        "JAM_HOME": tempfile.mkdtemp(),
    })
    # reclaim uses git_repo_root() which needs us to be in the repo
    # so let's invoke with the repo name approach by setting JAM_HOME
    # Actually, let's just pass the path directly via monkeypatch.

    # Use helpers.run directly to check pre-conditions
    r = subprocess.run(
        "git log --all --format=%ae", shell=True,
        capture_output=True, text=True, cwd=repo,
    )
    assert "anthropic.com" in r.stdout, "Test setup: should have anthropic commits"

    # Patch git_repo_root to return our test repo
    import unittest.mock as mock
    with mock.patch("jam.commands.reclaim.helpers.git_repo_root", return_value=repo):
        with mock.patch("jam.commands.reclaim.helpers.get_jam_config", return_value=None):
            # First reclaim
            result = runner.invoke(main, ["reclaim"], input="yes\n")
            assert result.exit_code == 0, result.output
            assert "Reclaimed" in result.output

            # Verify emails changed
            r = subprocess.run(
                "git log --all --format=%ae", shell=True,
                capture_output=True, text=True, cwd=repo,
            )
            assert "anthropic.com" not in r.stdout

            # Second reclaim — should be a no-op
            result = runner.invoke(main, ["reclaim"], input="yes\n")
            assert result.exit_code == 0, result.output
            assert "Nothing to reclaim" in result.output


def test_reclaim_commits_limit():
    """--commits N should only reclaim the last N commits."""
    repo = _make_repo_with_anthropic_commits()
    # repo has 4 commits: 1 user + 3 anthropic (ai commit 0, 1, 2)
    runner = CliRunner()

    import unittest.mock as mock
    with mock.patch("jam.commands.reclaim.helpers.git_repo_root", return_value=repo):
        with mock.patch("jam.commands.reclaim.helpers.get_jam_config", return_value=None):
            # Reclaim only the last 2 commits (ai commit 1 and 2)
            result = runner.invoke(
                main, ["reclaim", "--commits", "2"], input="yes\n",
            )
            assert result.exit_code == 0, result.output
            assert "2 commit(s) to reclaim" in result.output

            # The oldest anthropic commit (ai commit 0) should still
            # have the anthropic email
            r = subprocess.run(
                "git log --format=%ae:%s", shell=True,
                capture_output=True, text=True, cwd=repo,
            )
            lines = r.stdout.strip().splitlines()
            # Find the "ai commit 0" line — should still be anthropic
            for line in lines:
                if "ai commit 0" in line:
                    assert "anthropic.com" in line, (
                        f"ai commit 0 should not have been reclaimed: {line}"
                    )
