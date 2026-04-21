from subprocess import CompletedProcess
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main


def ok(stdout=""):
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def err(stderr="error"):
    return CompletedProcess(args=[], returncode=1, stdout="", stderr=stderr)


def _set_up_repo(tmp_path, name, origin_name=None):
    """Create a fake local git repo with a configurable origin URL."""
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    origin = origin_name if origin_name is not None else name
    return repo, f"https://github.com/testuser/{origin}.git"


@patch("os.rename")
@patch("jam.helpers.run")
def test_rename_happy_path(mock_run, mock_os_rename, tmp_path):
    _, origin_url = _set_up_repo(tmp_path, "myrepo")

    mock_run.side_effect = [
        ok(origin_url),  # git config --get remote.origin.url
        ok("testuser"),  # gh api user
        err(),           # gh repo view (target doesn't exist — good)
        ok(),            # gh repo rename
        ok(),            # git remote set-url
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code == 0, result.output
    assert "Renamed myrepo to newrepo" in result.output
    mock_os_rename.assert_called_once_with(
        str(tmp_path / "myrepo"), str(tmp_path / "newrepo")
    )
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("gh repo rename newrepo --yes" in c for c in calls)


@patch("jam.helpers.run")
def test_rename_fails_when_repo_missing(mock_run, tmp_path):
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "nope"], input="newrepo\n")
    assert result.exit_code != 0
    assert "not found" in (result.output + (result.stderr or ""))
    mock_run.assert_not_called()


@patch("jam.helpers.run")
def test_rename_fails_when_not_a_git_repo(mock_run, tmp_path):
    # Directory exists but no .git subdir
    (tmp_path / "myrepo").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code != 0
    assert "not a git repo" in result.output
    mock_run.assert_not_called()


@patch("os.rename")
@patch("jam.helpers.run")
def test_rename_rejects_when_remote_name_differs(mock_run, mock_os_rename, tmp_path):
    """If origin URL points at a different repo name, refuse without hitting the network."""
    _set_up_repo(tmp_path, "myrepo", origin_name="renamed-elsewhere")

    mock_run.side_effect = [
        ok("https://github.com/testuser/renamed-elsewhere.git"),  # git config
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code != 0
    assert "does not match" in result.output
    # Exactly one call: the git config read. No gh calls.
    assert mock_run.call_count == 1
    mock_os_rename.assert_not_called()


@patch("jam.helpers.run")
def test_rename_rejects_when_no_origin(mock_run, tmp_path):
    _set_up_repo(tmp_path, "myrepo")

    mock_run.side_effect = [err("")]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code != 0
    assert "no origin remote" in result.output


@patch("jam.helpers.run")
def test_rename_rejects_empty_new_name(mock_run, tmp_path):
    _set_up_repo(tmp_path, "myrepo")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    # click.prompt re-prompts on empty; send one empty then ctrl-d
    result = runner.invoke(main, ["rename", "myrepo"], input="\n\n\n\n")
    assert result.exit_code != 0
    mock_run.assert_not_called()


@patch("jam.helpers.run")
def test_rename_rejects_same_name(mock_run, tmp_path):
    _set_up_repo(tmp_path, "myrepo")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="myrepo\n")
    assert result.exit_code != 0
    assert "same as the current name" in result.output
    mock_run.assert_not_called()


@patch("jam.helpers.run")
def test_rename_rejects_invalid_characters(mock_run, tmp_path):
    _set_up_repo(tmp_path, "myrepo")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="bad name\n")
    assert result.exit_code != 0
    assert "Invalid name" in result.output
    mock_run.assert_not_called()


@patch("jam.helpers.run")
def test_rename_rejects_local_collision(mock_run, tmp_path):
    _set_up_repo(tmp_path, "myrepo")
    (tmp_path / "newrepo").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code != 0
    assert "already exists" in result.output
    mock_run.assert_not_called()


@patch("jam.helpers.run")
def test_rename_rejects_remote_collision(mock_run, tmp_path):
    _, origin_url = _set_up_repo(tmp_path, "myrepo")

    mock_run.side_effect = [
        ok(origin_url),  # git config
        ok("testuser"),  # gh api user
        ok(),            # gh repo view (exists — collision)
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="taken\n")
    assert result.exit_code != 0
    assert "already exists on GitHub" in result.output


@patch("jam.helpers.run")
def test_rename_propagates_gh_rename_failure(mock_run, tmp_path):
    _, origin_url = _set_up_repo(tmp_path, "myrepo")

    mock_run.side_effect = [
        ok(origin_url),  # git config
        ok("testuser"),  # gh api user
        err(),           # gh repo view (available)
        err("api error"),  # gh repo rename fails
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "myrepo"], input="newrepo\n")
    assert result.exit_code != 0
    assert "GitHub rename failed" in result.output


@patch("os.rename")
@patch("jam.helpers.run")
def test_rename_supports_prefix_matching(mock_run, mock_os_rename, tmp_path):
    """jam rename my-p → resolves to my-project."""
    _, origin_url = _set_up_repo(tmp_path, "my-project")

    mock_run.side_effect = [
        ok(origin_url),
        ok("testuser"),
        err(),
        ok(),
        ok(),
    ]

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["rename", "my-p"], input="newrepo\n")
    assert result.exit_code == 0, result.output
    assert "Renamed my-project to newrepo" in result.output
