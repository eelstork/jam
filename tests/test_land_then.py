import os
import sys
from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def err(stderr="error"):
    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


BRANCHES_OUTPUT = "origin/feat-branch\norigin/main\n"
COMMITS_OUTPUT = "abc1234 first commit\ndef5678 second commit\n"


@patch("subprocess.run")
@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_ldeploy_runs_land_then_script(
    mock_config, mock_isdir, mock_run, mock_head, mock_crumb, mock_subprocess, tmp_path
):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash")

    mock_run.side_effect = [
        ok(),                   # git fetch
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        ok(),                   # git push
    ]
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "Landed 2 commits from feat-branch" in result.output
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == ["bash", os.path.join(str(repo), "deploy.sh")]
    assert call_args[1]["cwd"] == str(repo)


@patch("subprocess.run")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_ldeploy_skips_script_when_nothing_to_land(
    mock_isdir, mock_run, mock_subprocess, tmp_path
):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash")

    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("origin/main\n"),    # for-each-ref: only main
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "No branches to land" in result.output
    mock_subprocess.assert_not_called()


@patch("subprocess.run")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_ldeploy_propagates_land_failure(
    mock_isdir, mock_run, mock_subprocess, tmp_path
):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash")

    mock_run.side_effect = [
        err("could not resolve host"),  # fetch fails
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy", "myrepo"])
    assert result.exit_code != 0
    assert "fetch failed" in result.output
    mock_subprocess.assert_not_called()


@patch("subprocess.run")
@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_ldeploy_forwards_extra_args(
    mock_config, mock_isdir, mock_run, mock_head, mock_crumb, mock_subprocess, tmp_path
):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash")

    mock_run.side_effect = [
        ok(), ok(BRANCHES_OUTPUT), ok(COMMITS_OUTPUT),
        ok(), ok(), ok(),
    ]
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy", "myrepo", "--prod", "v2"])
    assert result.exit_code == 0, result.output
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == [
        "bash",
        os.path.join(str(repo), "deploy.sh"),
        "--prod",
        "v2",
    ]


def test_lcmd_requires_repo_arg(tmp_path):
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy"])
    assert result.exit_code != 0
    assert "Usage" in (result.output + (result.stderr or ""))


@patch("subprocess.run")
@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_ldeploy_script_failure_propagates(
    mock_config, mock_isdir, mock_run, mock_head, mock_crumb, mock_subprocess, tmp_path
):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash")

    mock_run.side_effect = [
        ok(), ok(BRANCHES_OUTPUT), ok(COMMITS_OUTPUT),
        ok(), ok(), ok(),
    ]
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=2)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["ldeploy", "myrepo"])
    assert result.exit_code == 2
    mock_subprocess.assert_called_once()
