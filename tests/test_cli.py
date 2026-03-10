import os
from subprocess import CompletedProcess
from unittest.mock import call, mock_open, patch

from click.testing import CliRunner

from jam.cli import main


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def err(stderr="error"):
    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


# --- new ---


@patch("jam.cli.run")
@patch("builtins.open", mock_open())
@patch("os.path.exists", return_value=False)
def test_new_creates_repo(mock_exists, mock_run):
    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        err(),           # gh repo view (doesn't exist — good)
        ok(),            # gh repo create
        ok(),            # git checkout -b main
        ok(),            # git add
        ok(),            # git commit
        ok(),            # git push
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["new", "myrepo", "a cool project"])
    assert result.exit_code == 0
    assert "Created testuser/myrepo" in result.output


@patch("jam.cli.run")
def test_new_fails_when_repo_exists(mock_run):
    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        ok(),            # gh repo view (exists — bad)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["new", "myrepo"])
    assert result.exit_code != 0


def test_new_fails_without_jam_home():
    runner = CliRunner(env={})
    result = runner.invoke(main, ["new", "myrepo"])
    assert result.exit_code != 0
    assert "JAM_HOME" in result.output or "JAM_HOME" in (result.stderr or "")


@patch("jam.cli.run")
@patch("builtins.open", mock_open())
@patch("os.path.exists", return_value=False)
def test_new_no_description(mock_exists, mock_run):
    mock_run.side_effect = [
        ok("testuser"), err(), ok(), ok(), ok(), ok(), ok(),
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["new", "myrepo"])
    assert result.exit_code == 0
    handle = open()
    written = "".join(c.args[0] for c in handle.write.call_args_list)
    assert "no description yet" in written


# --- up ---


@patch("jam.cli.run")
@patch("os.path.isdir", return_value=True)
def test_up_with_name(mock_isdir, mock_run):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    assert "Pushed" in result.output
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")
    mock_run.assert_any_call('git commit -m "fix stuff"', cwd="/tmp/dev/myrepo")


@patch("jam.cli.run")
@patch("os.path.isdir", return_value=True)
def test_up_force_push(mock_isdir, mock_run):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "--force", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git push --force", cwd="/tmp/dev/myrepo")


@patch("jam.cli.run")
@patch("os.getcwd", return_value="/tmp/dev/myrepo")
def test_up_without_name_uses_cwd(mock_cwd, mock_run):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")


# --- down ---


@patch("jam.cli.run")
@patch("os.path.isdir", return_value=True)
def test_down_with_name(mock_isdir, mock_run):
    mock_run.side_effect = [ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "myrepo"])
    assert result.exit_code == 0
    assert "Pulled" in result.output
    mock_run.assert_any_call("git pull", cwd="/tmp/dev/myrepo")


@patch("jam.cli.run")
@patch("os.path.isdir", return_value=True)
def test_down_force(mock_isdir, mock_run):
    mock_run.side_effect = [ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "--force", "myrepo"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git reset --hard HEAD", cwd="/tmp/dev/myrepo")


@patch("jam.cli.run")
@patch("os.getcwd", return_value="/tmp/dev/myrepo")
def test_down_without_name_uses_cwd(mock_cwd, mock_run):
    mock_run.side_effect = [ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down"])
    assert result.exit_code == 0


# --- list ---


def test_list_repos(tmp_path):
    repo = tmp_path / "myrepo" / ".git"
    repo.mkdir(parents=True)
    notrepo = tmp_path / "notarepo"
    notrepo.mkdir()
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert "myrepo" in result.output
    assert "notarepo" not in result.output


def test_list_with_info(tmp_path):
    repo = tmp_path / "eliz-ai" / ".git"
    repo.mkdir(parents=True)
    readme = tmp_path / "eliz-ai" / "README.md"
    readme.write_text("# eliz-ai\n\none stop psy for cogs on the edge\n")
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["list", "--info"])
    assert result.exit_code == 0
    assert "eliz-ai \u2014 one stop psy for cogs on the edge" in result.output


def test_list_info_no_readme(tmp_path):
    repo = tmp_path / "bare" / ".git"
    repo.mkdir(parents=True)
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["list", "--info"])
    assert result.exit_code == 0
    assert "bare" in result.output
    assert "\u2014" not in result.output


# --- clone ---


@patch("jam.cli.run")
@patch("shutil.copytree")
@patch("builtins.open", mock_open())
@patch("os.path.exists", return_value=False)
@patch("os.path.isdir", return_value=True)
def test_clone_creates_new_repo(mock_isdir, mock_exists, mock_copy, mock_run):
    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        err(),           # gh repo view (doesn't exist — good)
        ok(),            # git init
        ok(),            # git checkout -b main
        ok(),            # gh repo create
        ok(),            # git remote add
        ok(),            # git add -A
        ok(),            # git commit
        ok(),            # git push
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "source", "target", "new desc"])
    assert result.exit_code == 0
    assert "Cloned source as testuser/target" in result.output


@patch("jam.cli.run")
@patch("os.path.isdir", return_value=True)
def test_clone_fails_when_target_exists(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        ok(),            # gh repo view (exists — bad)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "source", "target"])
    assert result.exit_code != 0
