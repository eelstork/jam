import json
import os
from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main
from jam.commands.allow_all import ALLOW_ALL_RULES


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def err(stderr="error"):
    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def _read(tmp_path, name):
    with open(tmp_path / name / ".claude" / "settings.json") as f:
        return json.load(f)


def _install(repo_path, extra_allow=()):
    """Helper: write settings.json with the allow-all rules present."""
    claude_dir = os.path.join(repo_path, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    settings = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {"allow": list(extra_allow) + list(ALLOW_ALL_RULES)},
    }
    with open(os.path.join(claude_dir, "settings.json"), "w") as f:
        json.dump(settings, f, indent=2)


def test_allow_all_adds_rules_to_repos(tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "notrepo").mkdir()

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0, result.output
    assert "Added allow-all permissions to 2 repos" in result.output

    for name in ("alpha", "beta"):
        allow = _read(tmp_path, name)["permissions"]["allow"]
        for rule in ALLOW_ALL_RULES:
            assert rule in allow
    assert not (tmp_path / "notrepo" / ".claude").exists()


def test_allow_all_covers_core_tools():
    for rule in ("Bash", "Read", "Edit", "Write", "WebFetch"):
        assert rule in ALLOW_ALL_RULES


def test_allow_all_idempotent(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        runner.invoke(main, ["allow-all"])
        result = runner.invoke(main, ["allow-all"])
    assert "Already installed: repo" in result.output

    allow = _read(tmp_path, "repo")["permissions"]["allow"]
    assert len(allow) == len(set(allow))
    assert set(allow) == set(ALLOW_ALL_RULES)


def test_allow_all_preserves_existing_settings(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    existing = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "attribution": {"commit": "alice", "pr": "alice"},
        "permissions": {
            "allow": ["Bash(npm *)"],
            "deny": ["Bash(rm -rf *)"],
            "defaultMode": "acceptEdits",
        },
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
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0, result.output

    settings = _read(tmp_path, "repo")
    assert settings["attribution"]["commit"] == "alice"
    assert settings["permissions"]["deny"] == ["Bash(rm -rf *)"]
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert settings["hooks"] == existing["hooks"]
    allow = settings["permissions"]["allow"]
    assert allow[0] == "Bash(npm *)"
    for rule in ALLOW_ALL_RULES:
        assert rule in allow


def test_allow_all_partial_rules_get_completed(tmp_path):
    """A repo with only some of the rules should get the rest, without dupes."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    with open(repo / ".claude" / "settings.json", "w") as f:
        json.dump({"permissions": {"allow": ["Bash", "Read"]}}, f)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert "Added allow-all permissions to 1 repo." in result.output

    allow = _read(tmp_path, "repo")["permissions"]["allow"]
    assert allow.count("Bash") == 1
    assert set(allow) == set(ALLOW_ALL_RULES)


def test_allow_all_schema_first(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        runner.invoke(main, ["allow-all"])

    keys = list(_read(tmp_path, "repo").keys())
    assert keys[0] == "$schema"


def test_allow_all_no_repos(tmp_path):
    (tmp_path / "notrepo").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0
    assert "Added allow-all permissions to 0 repos" in result.output


def test_allow_all_commits_and_pushes(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("git add" in c and "settings.json" in c for c in cmds)
    assert any("git commit" in c and "allow-all" in c for c in cmds)
    assert any("git push" in c for c in cmds)


def test_allow_all_no_commit_when_already_installed(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0
    assert "Already installed: repo" in result.output

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert not any("git commit" in c for c in cmds)
    assert not any("git push" in c for c in cmds)


def test_allow_all_aborts_if_any_dirty(tmp_path):
    (tmp_path / "pristine" / ".git").mkdir(parents=True)
    (tmp_path / "messy" / ".git").mkdir(parents=True)

    def run_side_effect(cmd, **kwargs):
        repo_name = os.path.basename(str(kwargs.get("cwd", "")))
        if repo_name == "messy" and "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code != 0
    assert "Aborted" in result.output
    assert "messy" in result.output

    for name in ("pristine", "messy"):
        assert not (tmp_path / name / ".claude" / "settings.json").exists()


def test_allow_all_dirty_repo_ok_if_installed(tmp_path):
    (tmp_path / "needs" / ".git").mkdir(parents=True)
    (tmp_path / "messy" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "messy"))

    def run_side_effect(cmd, **kwargs):
        repo_name = os.path.basename(str(kwargs.get("cwd", "")))
        if repo_name == "messy" and "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all"])
    assert result.exit_code == 0
    assert "Added allow-all permissions to 1 repo." in result.output
    assert "Already installed: messy" in result.output


# --unset tests


def test_unset_removes_rules(tmp_path):
    for name in ("alpha", "beta"):
        (tmp_path / name / ".git").mkdir(parents=True)
        _install(str(tmp_path / name))

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", "--unset"])
    assert result.exit_code == 0
    assert "Removed allow-all permissions from 2 repos" in result.output

    for name in ("alpha", "beta"):
        assert "permissions" not in _read(tmp_path, name)


def test_unset_preserves_other_rules(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _install(str(repo), extra_allow=["Bash(npm *)"])
    with open(repo / ".claude" / "settings.json") as f:
        settings = json.load(f)
    settings["permissions"]["deny"] = ["Bash(rm -rf *)"]
    settings["attribution"] = {"commit": "alice"}
    with open(repo / ".claude" / "settings.json", "w") as f:
        json.dump(settings, f)

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", "--unset"])
    assert result.exit_code == 0

    settings = _read(tmp_path, "repo")
    assert settings["attribution"]["commit"] == "alice"
    assert settings["permissions"]["allow"] == ["Bash(npm *)"]
    assert settings["permissions"]["deny"] == ["Bash(rm -rf *)"]


def test_unset_skips_repos_without_rules(tmp_path):
    (tmp_path / "norules" / ".git").mkdir(parents=True)
    (tmp_path / "hasrules" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "hasrules"))

    with patch("jam.helpers.run", return_value=ok()):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", "--unset"])
    assert result.exit_code == 0
    assert "Removed allow-all permissions from 1 repo." in result.output
    assert "Already removed: norules" in result.output


def test_unset_commits_and_pushes(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    with patch("jam.helpers.run", return_value=ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", "--unset"])
    assert result.exit_code == 0

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("git commit" in c and "remove" in c for c in cmds)
    assert any("git push" in c for c in cmds)


def test_unset_aborts_if_dirty(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    def run_side_effect(cmd, **kwargs):
        if "git diff" in cmd:
            return err()
        return ok()

    with patch("jam.helpers.run", side_effect=run_side_effect):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", "--unset"])
    assert result.exit_code != 0
    assert "Aborted" in result.output
