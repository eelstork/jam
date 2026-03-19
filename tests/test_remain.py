import json
import os
from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main
from jam.commands.remain import REMAIN_HOOK_COMMAND


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def err(stderr="error"):
    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def test_remain_adds_hook_to_repos(tmp_path):
    """remain should add the SessionStart hook to every repo."""
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "notrepo").mkdir()

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0
    assert "Added remain hook to 2 repos" in result.output

    for name in ("alpha", "beta"):
        settings_path = tmp_path / name / ".claude" / "settings.json"
        assert settings_path.exists()
        with open(settings_path) as f:
            settings = json.load(f)
        hooks = settings["hooks"]["SessionStart"]
        commands = [h["command"] for event in hooks for h in event["hooks"]]
        assert REMAIN_HOOK_COMMAND in commands


def test_remain_idempotent(tmp_path):
    """Running remain twice should not duplicate the hook."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        runner.invoke(main, ["remain"])
        runner.invoke(main, ["remain"])

    settings_path = tmp_path / "repo" / ".claude" / "settings.json"
    with open(settings_path) as f:
        settings = json.load(f)
    hooks = settings["hooks"]["SessionStart"]
    commands = [h["command"] for event in hooks for h in event["hooks"]]
    assert commands.count(REMAIN_HOOK_COMMAND) == 1


def test_remain_preserves_existing_settings(tmp_path):
    """remain should not clobber existing settings."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    existing = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "attribution": {"commit": "alice", "pr": "alice"},
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "echo hello"}]}
            ]
        },
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(existing, f)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0

    with open(claude_dir / "settings.json") as f:
        settings = json.load(f)

    # Existing attribution preserved
    assert settings["attribution"]["commit"] == "alice"
    # Existing hook preserved
    hooks = settings["hooks"]["SessionStart"]
    commands = [h["command"] for event in hooks for h in event["hooks"]]
    assert "echo hello" in commands
    assert REMAIN_HOOK_COMMAND in commands


def test_remain_no_repos(tmp_path):
    """remain with no repos should report 0."""
    (tmp_path / "notrepo").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0
    assert "Added remain hook to 0 repos" in result.output


def test_remain_schema_first(tmp_path):
    """The $schema key should be first in the output."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        runner.invoke(main, ["remain"])

    settings_path = tmp_path / "repo" / ".claude" / "settings.json"
    with open(settings_path) as f:
        settings = json.load(f)
    keys = list(settings.keys())
    assert keys[0] == "$schema"


def test_remain_singular_message(tmp_path):
    """Should use singular 'repo' for 1 repo."""
    (tmp_path / "solo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert "Added remain hook to 1 repo." in result.output


def test_remain_shows_progress_dots(tmp_path):
    """remain should print a dot per repo for progress."""
    (tmp_path / "aaa" / ".git").mkdir(parents=True)
    (tmp_path / "bbb" / ".git").mkdir(parents=True)
    (tmp_path / "ccc" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0
    assert "..." in result.output


def test_remain_commits_and_pushes(tmp_path):
    """remain should git add, commit, and push for each repo."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("git add" in c for c in cmds)
    assert any("git commit" in c for c in cmds)
    assert any("git push" in c for c in cmds)


def test_remain_no_commit_when_already_installed(tmp_path):
    """If the hook is already present, no commit/push should happen."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    existing = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": REMAIN_HOOK_COMMAND}]}
            ]
        }
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(existing, f)

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0
    assert "Already installed: repo" in result.output

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert not any("git commit" in c for c in cmds)
    assert not any("git push" in c for c in cmds)


def test_remain_aborts_if_any_dirty(tmp_path):
    """remain should abort entirely if any repo needing the hook is dirty."""
    (tmp_path / "pristine" / ".git").mkdir(parents=True)
    (tmp_path / "messy" / ".git").mkdir(parents=True)

    def run_side_effect(cmd, **kwargs):
        cwd = str(kwargs.get("cwd", ""))
        repo_name = os.path.basename(cwd)
        if repo_name == "messy" and "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code != 0
    assert "Aborted" in result.output
    assert "messy" in result.output

    # Neither repo should have been modified
    for name in ("pristine", "messy"):
        settings_path = tmp_path / name / ".claude" / "settings.json"
        assert not settings_path.exists()


def test_remain_dirty_repo_ok_if_hook_installed(tmp_path):
    """A dirty repo that already has the hook should not block remain."""
    (tmp_path / "needshook" / ".git").mkdir(parents=True)

    # This repo is dirty but already has the hook
    messy = tmp_path / "messy"
    (messy / ".git").mkdir(parents=True)
    claude_dir = messy / ".claude"
    claude_dir.mkdir()
    existing = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": REMAIN_HOOK_COMMAND}]}
            ]
        }
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(existing, f)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain"])
    assert result.exit_code == 0
    assert "Added remain hook to 1 repo." in result.output
    assert "Already installed: messy" in result.output


# --unset tests


def _install_hook(repo_path):
    """Helper: write settings.json with the remain hook installed."""
    claude_dir = os.path.join(repo_path, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    settings = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": REMAIN_HOOK_COMMAND}]}
            ]
        },
    }
    with open(os.path.join(claude_dir, "settings.json"), "w") as f:
        json.dump(settings, f, indent=2)


def test_unset_removes_hook(tmp_path):
    """--unset should remove the remain hook from all repos."""
    for name in ("alpha", "beta"):
        (tmp_path / name / ".git").mkdir(parents=True)
        _install_hook(str(tmp_path / name))

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0
    assert "Removed remain hook from 2 repos" in result.output

    for name in ("alpha", "beta"):
        with open(tmp_path / name / ".claude" / "settings.json") as f:
            settings = json.load(f)
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        commands = [
            h["command"] for event in session_start for h in event["hooks"]
        ]
        assert REMAIN_HOOK_COMMAND not in commands


def test_unset_preserves_other_hooks(tmp_path):
    """--unset should only remove the remain hook, leaving others intact."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    settings = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "attribution": {"commit": "alice"},
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "echo hello"}]},
                {"hooks": [{"type": "command", "command": REMAIN_HOOK_COMMAND}]},
            ]
        },
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(settings, f)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0

    with open(claude_dir / "settings.json") as f:
        settings = json.load(f)
    assert settings["attribution"]["commit"] == "alice"
    commands = [
        h["command"]
        for event in settings["hooks"]["SessionStart"]
        for h in event["hooks"]
    ]
    assert "echo hello" in commands
    assert REMAIN_HOOK_COMMAND not in commands


def test_unset_cleans_up_empty_hooks(tmp_path):
    """--unset should remove empty hooks/SessionStart keys."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _install_hook(str(repo))

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0

    with open(repo / ".claude" / "settings.json") as f:
        settings = json.load(f)
    assert "hooks" not in settings


def test_unset_skips_repos_without_hook(tmp_path):
    """--unset should skip repos that don't have the hook."""
    (tmp_path / "nohook" / ".git").mkdir(parents=True)
    (tmp_path / "hashook" / ".git").mkdir(parents=True)
    _install_hook(str(tmp_path / "hashook"))

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0
    assert "Removed remain hook from 1 repo." in result.output
    assert "Already removed: nohook" in result.output


def test_unset_commits_and_pushes(tmp_path):
    """--unset should git add, commit, and push."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install_hook(str(tmp_path / "repo"))

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("git add" in c for c in cmds)
    assert any("git commit" in c and "remove" in c for c in cmds)
    assert any("git push" in c for c in cmds)


def test_unset_aborts_if_dirty(tmp_path):
    """--unset should abort if a repo with the hook has dirty state."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install_hook(str(tmp_path / "repo"))

    def run_side_effect(cmd, **kwargs):
        if "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code != 0
    assert "Aborted" in result.output


def test_unset_dirty_ok_if_no_hook(tmp_path):
    """--unset should not be blocked by a dirty repo that lacks the hook."""
    # This repo has the hook — needs removal
    (tmp_path / "hashook" / ".git").mkdir(parents=True)
    _install_hook(str(tmp_path / "hashook"))

    # This repo is dirty but doesn't have the hook — no work needed
    (tmp_path / "nohook" / ".git").mkdir(parents=True)

    def run_side_effect(cmd, **kwargs):
        cwd = str(kwargs.get("cwd", ""))
        repo_name = os.path.basename(cwd)
        if repo_name == "nohook" and "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remain", "--unset"])
    assert result.exit_code == 0
    assert "Removed remain hook from 1 repo." in result.output
