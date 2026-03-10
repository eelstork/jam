import os
import sys
from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main
from jam.commands.run_script import _find_script, _build_argv


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


# --- _find_script precedence ---


def test_find_script_sh_preferred_on_unix(tmp_path):
    (tmp_path / "deploy.sh").write_text("#!/bin/bash")
    (tmp_path / "deploy.py").write_text("pass")
    with patch("jam.commands.run_script._is_windows", return_value=False):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.sh")


def test_find_script_py_when_no_sh_on_unix(tmp_path):
    (tmp_path / "deploy.py").write_text("pass")
    with patch("jam.commands.run_script._is_windows", return_value=False):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.py")


def test_find_script_ps1_last_resort_on_unix(tmp_path):
    (tmp_path / "deploy.ps1").write_text("Write-Host hi")
    with patch("jam.commands.run_script._is_windows", return_value=False):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.ps1")


def test_find_script_ps1_preferred_on_windows(tmp_path):
    (tmp_path / "deploy.ps1").write_text("Write-Host hi")
    (tmp_path / "deploy.py").write_text("pass")
    with patch("jam.commands.run_script._is_windows", return_value=True):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.ps1")


def test_find_script_py_when_no_ps1_on_windows(tmp_path):
    (tmp_path / "deploy.py").write_text("pass")
    with patch("jam.commands.run_script._is_windows", return_value=True):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.py")


def test_find_script_sh_last_resort_on_windows(tmp_path):
    (tmp_path / "deploy.sh").write_text("#!/bin/bash")
    with patch("jam.commands.run_script._is_windows", return_value=True):
        result = _find_script(str(tmp_path), "deploy")
    assert result.endswith("deploy.sh")


def test_find_script_none_when_missing(tmp_path):
    with patch("jam.commands.run_script._is_windows", return_value=False):
        result = _find_script(str(tmp_path), "deploy")
    assert result is None


# --- _build_argv ---


def test_build_argv_py():
    argv = _build_argv("/repo/test.py")
    assert argv == [sys.executable, "/repo/test.py"]


def test_build_argv_sh():
    argv = _build_argv("/repo/test.sh")
    assert argv == ["bash", "/repo/test.sh"]


def test_build_argv_ps1():
    argv = _build_argv("/repo/test.ps1")
    assert argv == ["powershell", "-ExecutionPolicy", "Bypass", "-File", "/repo/test.ps1"]


# --- integration: jam CMD (current repo) ---


@patch("subprocess.run")
@patch("jam.helpers.run")
def test_unknown_cmd_runs_script(mock_helpers_run, mock_subprocess, tmp_path):
    (tmp_path / "deploy.py").write_text("print('deploying')")

    mock_helpers_run.return_value = ok(str(tmp_path))
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner()
    result = runner.invoke(main, ["deploy"])
    assert result.exit_code == 0
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == [sys.executable, os.path.join(str(tmp_path), "deploy.py")]
    assert call_args[1]["cwd"] == str(tmp_path)


@patch("subprocess.run")
@patch("jam.helpers.run")
def test_script_receives_extra_args(mock_helpers_run, mock_subprocess, tmp_path):
    (tmp_path / "build.sh").write_text("#!/bin/bash")

    mock_helpers_run.return_value = ok(str(tmp_path))
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner()
    result = runner.invoke(main, ["build", "--release", "v2"])
    assert result.exit_code == 0
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == ["bash", os.path.join(str(tmp_path), "build.sh"),
                                "--release", "v2"]


@patch("jam.helpers.run")
def test_unknown_cmd_no_script_fails(mock_helpers_run, tmp_path):
    mock_helpers_run.return_value = ok(str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(main, ["nonexistent"])
    assert result.exit_code != 0


def test_builtin_takes_precedence_over_script(tmp_path):
    """Even if root.py exists, `jam root` runs the built-in."""
    (tmp_path / "root.py").write_text("print('nope')")

    with patch("jam.helpers.run", return_value=ok(str(tmp_path))):
        runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
        result = runner.invoke(main, ["root"])
    assert result.exit_code == 0
    assert "/tmp/dev" in result.output


# --- integration: jam CMD REPO (named repo) ---


@patch("subprocess.run")
def test_cmd_with_repo_name(mock_subprocess, tmp_path):
    """jam deploy myrepo -> runs myrepo/deploy.sh"""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "deploy.sh").write_text("#!/bin/bash\necho deploying")

    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["deploy", "myrepo"])
    assert result.exit_code == 0
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == ["bash", os.path.join(str(repo), "deploy.sh")]
    assert call_args[1]["cwd"] == str(repo)


@patch("subprocess.run")
def test_cmd_with_repo_name_and_args(mock_subprocess, tmp_path):
    """jam build myrepo --release -> runs myrepo/build.py --release"""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "build.py").write_text("pass")

    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["build", "myrepo", "--release"])
    assert result.exit_code == 0
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == [sys.executable, os.path.join(str(repo), "build.py"),
                                "--release"]


def test_cmd_with_repo_name_no_script(tmp_path):
    """jam deploy myrepo -> error if myrepo has no deploy script."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["deploy", "myrepo"])
    assert result.exit_code != 0
    assert "No script" in result.output or "No script" in (result.stderr or "")


@patch("subprocess.run")
@patch("jam.helpers.run")
def test_non_repo_arg_treated_as_script_arg(mock_helpers_run, mock_subprocess, tmp_path):
    """jam build notarepo -> 'notarepo' is not a repo, passed as arg to script."""
    (tmp_path / "build.sh").write_text("#!/bin/bash")

    mock_helpers_run.return_value = ok(str(tmp_path))
    mock_subprocess.return_value = CompletedProcess(args=[], returncode=0)

    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["build", "notarepo"])
    assert result.exit_code == 0
    call_args = mock_subprocess.call_args
    # "notarepo" should be passed as an arg to the script, not used as repo
    assert call_args[0][0] == ["bash", os.path.join(str(tmp_path), "build.sh"),
                                "notarepo"]
