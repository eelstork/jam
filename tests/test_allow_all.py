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


def git_ok(branch="main", ahead="0", overrides=None):
    """A helpers.run stand-in for a clean repo on *branch* with no unpushed commits.

    overrides maps a substring of the command to a callable(cmd, kwargs) -> result.
    """
    overrides = overrides or {}

    def side_effect(cmd, **kwargs):
        for key, fn in overrides.items():
            if key in cmd:
                return fn(cmd, kwargs)
        if "branch --show-current" in cmd:
            return ok(branch + "\n")
        if "rev-list --count" in cmd:
            return ok(ahead + "\n")
        return ok()

    return side_effect


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


def _invoke(tmp_path, *args, side_effect=None):
    with patch("jam.helpers.run", side_effect=side_effect or git_ok()) as mock_run:
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["allow-all", *args])
    return result, [c.args[0] for c in mock_run.call_args_list]


def test_allow_all_adds_rules_to_repos(tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "notrepo").mkdir()

    result, _ = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "alpha: added" in result.output
    assert "beta: added" in result.output
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

    _invoke(tmp_path)
    result, cmds = _invoke(tmp_path)
    assert "Already installed: repo" in result.output
    assert not any("git commit" in c for c in cmds)

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

    result, _ = _invoke(tmp_path)
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

    result, _ = _invoke(tmp_path)
    assert "Added allow-all permissions to 1 repo." in result.output

    allow = _read(tmp_path, "repo")["permissions"]["allow"]
    assert allow.count("Bash") == 1
    assert set(allow) == set(ALLOW_ALL_RULES)


def test_allow_all_schema_first(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _invoke(tmp_path)
    keys = list(_read(tmp_path, "repo").keys())
    assert keys[0] == "$schema"


def test_allow_all_no_repos(tmp_path):
    (tmp_path / "notrepo").mkdir()
    result, _ = _invoke(tmp_path)
    assert result.exit_code == 0
    assert "Added allow-all permissions to 0 repos" in result.output


def test_allow_all_workflow_order(tmp_path):
    """Branch check, pull, ahead check, add, commit, push -- in that order."""
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, cmds = _invoke(tmp_path)
    assert result.exit_code == 0

    def idx(sub):
        return next(i for i, c in enumerate(cmds) if sub in c)

    assert idx("branch --show-current") < idx("git pull")
    assert "--ff-only" in cmds[idx("git pull")]
    assert idx("git pull") < idx("rev-list --count")
    assert idx("rev-list --count") < idx("git add")
    assert "settings.json" in cmds[idx("git add")]
    assert idx("git add") < idx("git commit")
    assert "allow-all" in cmds[idx("git commit")]
    assert idx("git commit") < idx("git push")


def test_allow_all_no_commit_when_already_installed(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    result, cmds = _invoke(tmp_path)
    assert result.exit_code == 0
    assert "Already installed: repo" in result.output
    assert not any("git pull" in c for c in cmds)
    assert not any("git commit" in c for c in cmds)
    assert not any("git push" in c for c in cmds)


def test_allow_all_skips_repo_not_on_main(tmp_path):
    (tmp_path / "feature" / ".git").mkdir(parents=True)
    (tmp_path / "onmain" / ".git").mkdir(parents=True)

    def branch(cmd, kwargs):
        name = os.path.basename(str(kwargs.get("cwd", "")))
        return ok("wip\n" if name == "feature" else "main\n")

    result, cmds = _invoke(
        tmp_path, side_effect=git_ok(overrides={"branch --show-current": branch})
    )
    assert result.exit_code == 0
    assert "feature: skipped, on branch wip, not main" in result.output
    assert "onmain: added" in result.output
    assert "Added allow-all permissions to 1 repo." in result.output
    assert "Skipped: feature" in result.output
    assert not (tmp_path / "feature" / ".claude").exists()


def test_allow_all_skips_when_settings_dirty(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, cmds = _invoke(
        tmp_path,
        side_effect=git_ok(
            overrides={"status --porcelain": lambda c, k: ok(" M .claude/settings.json\n")}
        ),
    )
    assert "repo: skipped, .claude/settings.json has uncommitted changes" in result.output
    assert not any("git pull" in c for c in cmds)
    assert not (tmp_path / "repo" / ".claude" / "settings.json").exists()


def test_allow_all_skips_when_pull_fails(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, cmds = _invoke(
        tmp_path,
        side_effect=git_ok(
            overrides={
                "git pull": lambda c, k: err("fatal: Not possible to fast-forward, aborting.")
            }
        ),
    )
    assert "repo: skipped, pull failed: fatal: Not possible to fast-forward, aborting." in result.output
    assert not any("git commit" in c for c in cmds)
    assert not (tmp_path / "repo" / ".claude").exists()


def test_allow_all_skips_when_unpushed_commits(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, cmds = _invoke(tmp_path, side_effect=git_ok(ahead="2"))
    assert "repo: skipped, 2 unpushed commits, push those first" in result.output
    assert not any("git commit" in c for c in cmds)
    assert not (tmp_path / "repo" / ".claude").exists()


def test_allow_all_skips_when_no_upstream(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, _ = _invoke(
        tmp_path,
        side_effect=git_ok(overrides={"rev-list --count": lambda c, k: err("fatal: no upstream")}),
    )
    assert "repo: skipped, no upstream branch" in result.output


def test_allow_all_reports_push_failure(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)

    result, _ = _invoke(
        tmp_path,
        side_effect=git_ok(
            overrides={"git push": lambda c, k: err("remote: Permission denied\nerror: failed to push")}
        ),
    )
    assert result.exit_code == 0
    assert "repo: skipped, push failed (commit is local): Permission denied" in result.output
    assert "Added allow-all permissions to 0 repos" in result.output
    # The edit was made and committed locally; it just didn't reach the remote.
    assert (tmp_path / "repo" / ".claude" / "settings.json").exists()


def test_reason_prefers_remote_then_fatal_then_last_line():
    from jam.commands.allow_all import _reason

    assert _reason(err("remote: hint: try again\nremote: nope, protected\nerror: failed")) == "nope, protected"
    assert _reason(err("some noise\nfatal: Not possible to fast-forward\nmore")) == "fatal: Not possible to fast-forward"
    assert _reason(err("just this")) == "just this"
    assert _reason(err("")) == "exit 1"


def test_allow_all_one_bad_repo_does_not_stop_others(tmp_path):
    (tmp_path / "bad" / ".git").mkdir(parents=True)
    (tmp_path / "good" / ".git").mkdir(parents=True)

    def pull(cmd, kwargs):
        name = os.path.basename(str(kwargs.get("cwd", "")))
        return err("conflict") if name == "bad" else ok()

    result, _ = _invoke(tmp_path, side_effect=git_ok(overrides={"git pull": pull}))
    assert result.exit_code == 0
    assert "bad: skipped, pull failed: conflict" in result.output
    assert "good: added" in result.output
    assert "Added allow-all permissions to 1 repo." in result.output


# --unset tests


def test_unset_removes_rules(tmp_path):
    for name in ("alpha", "beta"):
        (tmp_path / name / ".git").mkdir(parents=True)
        _install(str(tmp_path / name))

    result, _ = _invoke(tmp_path, "--unset")
    assert result.exit_code == 0
    assert "alpha: removed" in result.output
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

    result, _ = _invoke(tmp_path, "--unset")
    assert result.exit_code == 0

    settings = _read(tmp_path, "repo")
    assert settings["attribution"]["commit"] == "alice"
    assert settings["permissions"]["allow"] == ["Bash(npm *)"]
    assert settings["permissions"]["deny"] == ["Bash(rm -rf *)"]


def test_unset_skips_repos_without_rules(tmp_path):
    (tmp_path / "norules" / ".git").mkdir(parents=True)
    (tmp_path / "hasrules" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "hasrules"))

    result, _ = _invoke(tmp_path, "--unset")
    assert result.exit_code == 0
    assert "Removed allow-all permissions from 1 repo." in result.output
    assert "Already removed: norules" in result.output


def test_unset_commits_and_pushes(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    result, cmds = _invoke(tmp_path, "--unset")
    assert result.exit_code == 0
    assert any("git commit" in c and "remove" in c for c in cmds)
    assert any("git push" in c for c in cmds)


def test_unset_skips_repo_not_on_main(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    _install(str(tmp_path / "repo"))

    result, cmds = _invoke(tmp_path, "--unset", side_effect=git_ok(branch="wip"))
    assert "repo: skipped, on branch wip, not main" in result.output
    assert not any("git commit" in c for c in cmds)
    allow = _read(tmp_path, "repo")["permissions"]["allow"]
    assert set(ALLOW_ALL_RULES) <= set(allow)
