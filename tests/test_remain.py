import json
import os
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main
from jam.commands.remain import REMAIN_HOOK_COMMAND


def test_remain_adds_hook_to_repos(tmp_path):
    """remain should add the SessionStart hook to every repo."""
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "notrepo").mkdir()

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

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["remain"])
    assert "Added remain hook to 1 repo." in result.output
