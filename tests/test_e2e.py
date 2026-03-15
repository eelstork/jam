"""End-to-end tests for jam — require gh CLI authenticated with repo access.

These tests create real GitHub repos with a ``jam-e2e-`` prefix and delete
them on teardown.  They are skipped automatically when ``gh`` is not available
or not authenticated.

Run locally::

    pytest tests/test_e2e.py -v
"""

import os
import shutil
import subprocess
import uuid

import pytest
from click.testing import CliRunner

from jam.cli import main

# ---------------------------------------------------------------------------
# Skip logic
# ---------------------------------------------------------------------------

def _gh_available():
    """Return True if gh CLI is installed and authenticated.

    If JAM_TEST_PAT is set, authenticate gh with it first.
    """
    pat = os.environ.get("JAM_TEST_PAT", "")
    if pat:
        try:
            subprocess.run(
                ["gh", "auth", "login", "--with-token"],
                input=pat, capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    try:
        r = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


if not _gh_available():
    pytest.skip(
        "gh CLI not authenticated — skipping e2e tests. "
        "Set JAM_TEST_PAT or run 'gh auth login' to enable.",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_PREFIX = "jam-e2e-"


def _gh_user():
    r = subprocess.run(
        ["gh", "api", "user", "-q", ".login"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, "Could not resolve gh user"
    return r.stdout.strip()


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    """Provide JAM_HOME, a CliRunner, and the GitHub username.

    Cleans up any jam-e2e- repos created during the session.
    """
    jam_home = str(tmp_path_factory.mktemp("jam_home"))
    user = _gh_user()
    runner = CliRunner(env={"JAM_HOME": jam_home})
    created_repos = []

    # Disable commit signing for the duration of the test run — the CI
    # environment may have signing enabled with a server that is
    # unavailable to the test process.
    _prev_gpgsign = subprocess.run(
        ["git", "config", "--global", "commit.gpgsign"],
        capture_output=True, text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "config", "--global", "commit.gpgsign", "false"],
        check=True,
    )

    # Let git use gh as credential helper so HTTPS pushes/pulls work
    # when only GH_TOKEN (or gh auth) is available.
    subprocess.run(["gh", "auth", "setup-git"], capture_output=True)

    class Env:
        pass

    e = Env()
    e.jam_home = jam_home
    e.user = user
    e.runner = runner
    e.created_repos = created_repos

    yield e

    # Teardown: restore git signing config
    if _prev_gpgsign:
        subprocess.run(
            ["git", "config", "--global", "commit.gpgsign", _prev_gpgsign],
            capture_output=True,
        )
    else:
        subprocess.run(
            ["git", "config", "--global", "--unset", "commit.gpgsign"],
            capture_output=True,
        )

    # Teardown: delete every remote repo we created
    for name in created_repos:
        subprocess.run(
            ["gh", "repo", "delete", f"{user}/{name}", "--yes"],
            capture_output=True,
        )


def _repo_name():
    return f"{REPO_PREFIX}{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Tests — run in order within the module
# ---------------------------------------------------------------------------

class TestLifecycle:
    """Sequential tests exercising the core jam workflow."""

    repo_name = _repo_name()
    repo2_name = _repo_name()

    # -- new ----------------------------------------------------------------

    def test_new(self, env):
        env.created_repos.append(self.repo_name)
        result = env.runner.invoke(main, ["new", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Created" in result.output

        repo_path = os.path.join(env.jam_home, self.repo_name)
        assert os.path.isdir(repo_path)
        assert os.path.isfile(os.path.join(repo_path, "README.md"))

    # -- up -----------------------------------------------------------------

    def test_up(self, env):
        repo_path = os.path.join(env.jam_home, self.repo_name)
        with open(os.path.join(repo_path, "hello.txt"), "w") as f:
            f.write("hello\n")

        result = env.runner.invoke(main, ["up", "add hello", "-n", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Pushed" in result.output

        # Verify the commit is in the log
        r = subprocess.run(
            "git log --oneline -1", shell=True, capture_output=True,
            text=True, cwd=repo_path,
        )
        assert "add hello" in r.stdout

    # -- down ---------------------------------------------------------------

    def test_down(self, env):
        result = env.runner.invoke(main, ["down", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Pulled" in result.output

    # -- undo up ------------------------------------------------------------

    def test_undo_up(self, env):
        repo_path = os.path.join(env.jam_home, self.repo_name)

        # Push something we'll undo
        with open(os.path.join(repo_path, "temp.txt"), "w") as f:
            f.write("temporary\n")
        result = env.runner.invoke(main, ["up", "temp commit", "-n", self.repo_name])
        assert result.exit_code == 0, result.output

        result = env.runner.invoke(main, ["undo", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Undid up" in result.output
        assert not os.path.exists(os.path.join(repo_path, "temp.txt"))

    # -- land ---------------------------------------------------------------

    def test_land(self, env):
        repo_path = os.path.join(env.jam_home, self.repo_name)

        # Create and push a feature branch
        subprocess.run("git checkout -b feat-test", shell=True, cwd=repo_path)
        with open(os.path.join(repo_path, "feature.txt"), "w") as f:
            f.write("feature\n")
        subprocess.run("git add -A", shell=True, cwd=repo_path)
        subprocess.run('git commit -m "add feature"', shell=True, cwd=repo_path)
        subprocess.run("git push -u origin feat-test", shell=True, cwd=repo_path)
        subprocess.run("git checkout main", shell=True, cwd=repo_path)

        result = env.runner.invoke(main, ["land", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Landed" in result.output

        # feature.txt should be on main now
        assert os.path.isfile(os.path.join(repo_path, "feature.txt"))

    # -- undo land ----------------------------------------------------------

    def test_undo_land(self, env):
        result = env.runner.invoke(main, ["undo", self.repo_name])
        assert result.exit_code == 0, result.output
        assert "Undid land" in result.output

        # feature.txt should be gone from main after undo
        repo_path = os.path.join(env.jam_home, self.repo_name)
        assert not os.path.exists(os.path.join(repo_path, "feature.txt"))

    # -- clone --------------------------------------------------------------

    def test_clone(self, env):
        env.created_repos.append(self.repo2_name)
        result = env.runner.invoke(
            main, ["clone", self.repo_name, self.repo2_name],
        )
        assert result.exit_code == 0, result.output
        assert "Cloned" in result.output

        repo2_path = os.path.join(env.jam_home, self.repo2_name)
        assert os.path.isdir(repo2_path)
        # Should have the README from the source
        assert os.path.isfile(os.path.join(repo2_path, "README.md"))

    # -- infuse -------------------------------------------------------------

    def test_infuse(self, env):
        # Add a unique file to repo1
        repo_path = os.path.join(env.jam_home, self.repo_name)
        with open(os.path.join(repo_path, "snippet.txt"), "w") as f:
            f.write("snippet\n")
        subprocess.run("git add -A", shell=True, cwd=repo_path)
        subprocess.run('git commit -m "add snippet"', shell=True, cwd=repo_path)

        # Use a subpath to avoid conflicts with files shared via clone
        result = env.runner.invoke(
            main, ["infuse", self.repo_name, "--into", f"{self.repo2_name}/imported"],
        )
        assert result.exit_code == 0, result.output
        assert "Infused" in result.output

        repo2_path = os.path.join(env.jam_home, self.repo2_name)
        assert os.path.isfile(os.path.join(repo2_path, "imported", "snippet.txt"))

    # -- delete -------------------------------------------------------------

    def test_delete(self, env):
        repo2_path = os.path.join(env.jam_home, self.repo2_name)
        result = env.runner.invoke(main, ["delete", self.repo2_name], input="y\n")
        assert result.exit_code == 0, result.output
        assert "Deleted" in result.output
        assert not os.path.isdir(repo2_path)


class TestCooldownAndStats:
    """Test cooldown and stats commands."""

    def test_cooldown(self, env):
        # TestLifecycle already pushed commits — cooldown should either
        # list them (if after 7am) or print the empty message.
        result = env.runner.invoke(main, ["cooldown"])
        assert result.exit_code == 0, result.output
        # We can't assert specific output since it depends on time of day,
        # but it must not crash.

    def test_stats(self, env):
        # Previous test invocations should have been logged.
        result = env.runner.invoke(main, ["stats"])
        assert result.exit_code == 0, result.output
        # We've run many commands already, so stats shouldn't be empty.
        assert "No usage data" not in result.output

    def test_stats_clear(self, env):
        result = env.runner.invoke(main, ["stats", "--clear"])
        assert result.exit_code == 0, result.output
        assert "cleared" in result.output

        # After clearing, stats should show no data.
        result = env.runner.invoke(main, ["stats"])
        assert result.exit_code == 0, result.output
        assert "No usage data" in result.output


class TestClaimAndReclaim:
    """Test claim-commits and reclaim workflows."""

    repo_name = _repo_name()

    def test_claim_commits(self, env):
        result = env.runner.invoke(main, ["claim-commits"], input="yes\n")
        assert result.exit_code == 0, result.output
        assert "attribution restored" in result.output.lower() or "Done" in result.output

        from jam import helpers
        assert helpers.get_jam_config("attribution_enabled") is True
        assert helpers.get_jam_config("claim_commits_done") is True

    def test_reclaim(self, env):
        env.created_repos.append(self.repo_name)

        # Create a repo with a commit from @anthropic.com
        result = env.runner.invoke(main, ["new", self.repo_name])
        assert result.exit_code == 0, result.output

        repo_path = os.path.join(env.jam_home, self.repo_name)

        # Since attribution_enabled was set by test_claim_commits,
        # jam new should have written .claude/settings.json
        settings_path = os.path.join(repo_path, ".claude", "settings.json")
        assert os.path.isfile(settings_path), ".claude/settings.json not created"
        import json
        with open(settings_path) as f:
            settings = json.load(f)
        assert settings["attribution"]["commit"] == ""
        assert settings["attribution"]["pr"] == ""

        # Set a non-anthropic identity in this repo so reclaim has a
        # real user to rewrite to (the CI global config may itself use
        # an @anthropic.com email).
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
        )
        subprocess.run(
            ["git", "config", "user.email", "testuser@example.com"],
            cwd=repo_path,
        )

        # Fake an anthropic-authored commit
        with open(os.path.join(repo_path, "ai.txt"), "w") as f:
            f.write("ai work\n")
        subprocess.run("git add -A", shell=True, cwd=repo_path)
        subprocess.run(
            'git -c user.name="Claude" -c user.email="claude@anthropic.com" '
            'commit -m "ai commit"',
            shell=True, cwd=repo_path,
        )

        # Verify it's currently authored by anthropic
        r = subprocess.run(
            "git log --format=%ae -1", shell=True,
            capture_output=True, text=True, cwd=repo_path,
        )
        assert "anthropic.com" in r.stdout

        result = env.runner.invoke(main, ["reclaim", self.repo_name], input="yes\n")
        assert result.exit_code == 0, result.output
        assert "Reclaimed" in result.output

        # Verify authorship was rewritten
        r = subprocess.run(
            "git log --format=%ae --all", shell=True,
            capture_output=True, text=True, cwd=repo_path,
        )
        assert "anthropic.com" not in r.stdout
