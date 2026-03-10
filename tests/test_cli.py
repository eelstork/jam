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


@patch("jam.helpers.run")
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


@patch("jam.helpers.run")
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


@patch("jam.helpers.run")
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


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_up_with_name(mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "--name", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    assert "Pushed" in result.output
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")
    mock_run.assert_any_call('git commit -m "fix stuff"', cwd="/tmp/dev/myrepo")
    mock_crumb.assert_called_once_with("/tmp/dev/myrepo", "up", pre_head="abc1234")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_up_force_push(mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "--force", "--name", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git push --force", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.getcwd", return_value="/tmp/dev/myrepo")
def test_up_without_name_uses_cwd(mock_cwd, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")


# --- down ---


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_down_with_name(mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "myrepo"])
    assert result.exit_code == 0
    assert "Pulled" in result.output
    mock_run.assert_any_call("git pull", cwd="/tmp/dev/myrepo")
    mock_crumb.assert_called_once_with("/tmp/dev/myrepo", "down", pre_head="abc1234")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_down_force(mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "--force", "myrepo"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git reset --hard HEAD", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.getcwd", return_value="/tmp/dev/myrepo")
def test_down_without_name_uses_cwd(mock_cwd, mock_run, mock_head, mock_crumb):
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


@patch("jam.helpers.run")
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


@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_clone_fails_when_target_exists(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        ok(),            # gh repo view (exists — bad)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "source", "target"])
    assert result.exit_code != 0


# --- land ---


BRANCHES_OUTPUT = "origin/feat-branch\norigin/main\n"
COMMITS_OUTPUT = "abc1234 first commit\ndef5678 second commit\nghi9012 third commit\njkl3456 fourth commit\n"


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_fast(mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        ok(),                   # git push
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "--fast", "myrepo"])
    assert result.exit_code == 0
    assert "Landed 4 commits from feat-branch" in result.output
    mock_crumb.assert_called_once_with("/tmp/dev/myrepo", "land", pre_head="abc1234")
    # land should NOT delete the branch (local or remote)
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert not any("branch -d" in c for c in cmds)
    assert not any("push origin --delete" in c for c in cmds)


@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_shows_3_commits_by_default(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"], input="n\n")
    assert "first commit" in result.output
    assert "second commit" in result.output
    assert "third commit" in result.output
    assert "fourth commit" not in result.output
    assert "... and 1 more" in result.output


@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_all_shows_all_commits(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "--all", "myrepo"], input="n\n")
    assert "first commit" in result.output
    assert "fourth commit" in result.output
    assert "... and" not in result.output


@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_no_branches(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("origin/main\n"),    # git for-each-ref (only main)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code != 0


# --- infuse ---


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run", return_value=ok())
def test_infuse_into_target(mock_run, mock_head, mock_crumb, tmp_path):
    src = tmp_path / "snippets"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "util.py").write_text("# util")
    (src / "lib").mkdir()
    (src / "lib" / "helper.py").write_text("# helper")
    (src / ".git" / "config").write_text("gitconfig")

    target = tmp_path / "myapp"
    target.mkdir()
    (target / ".git").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["infuse", "snippets", "--into", "myapp"])
    assert result.exit_code == 0
    assert "Infused 2 files" in result.output
    assert (target / "util.py").read_text() == "# util"
    assert (target / "lib" / "helper.py").read_text() == "# helper"
    assert not (target / ".git" / "config").exists()
    mock_crumb.assert_called_once()


def test_infuse_conflict(tmp_path):
    src = tmp_path / "snippets"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "readme.txt").write_text("from source")

    target = tmp_path / "myapp"
    target.mkdir()
    (target / ".git").mkdir()
    (target / "readme.txt").write_text("already here")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["infuse", "snippets", "--into", "myapp"])
    assert result.exit_code != 0
    assert "readme.txt" in result.output
    assert (target / "readme.txt").read_text() == "already here"


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run", return_value=ok())
def test_infuse_src_from_cwd(mock_run, mock_head, mock_crumb, tmp_path, monkeypatch):
    src = tmp_path / "snippets"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "data.txt").write_text("data")

    target = tmp_path / "myapp"
    target.mkdir()
    (target / ".git").mkdir()

    monkeypatch.setenv("JAM_HOME", str(tmp_path))
    monkeypatch.chdir(target)

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["infuse", "snippets"])
    assert result.exit_code == 0
    assert "Infused 1 file" in result.output
    assert (target / "data.txt").read_text() == "data"


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run", return_value=ok())
def test_infuse_into_subpath(mock_run, mock_head, mock_crumb, tmp_path):
    src = tmp_path / "snippets"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "util.py").write_text("# util")
    (src / "sub").mkdir()
    (src / "sub" / "deep.py").write_text("# deep")

    target = tmp_path / "myapp"
    target.mkdir()
    (target / ".git").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["infuse", "snippets", "--into", "myapp/vendor/ext"])
    assert result.exit_code == 0
    assert "Infused 2 files from snippets into myapp/vendor/ext" in result.output
    assert (target / "vendor" / "ext" / "util.py").read_text() == "# util"
    assert (target / "vendor" / "ext" / "sub" / "deep.py").read_text() == "# deep"


def test_infuse_into_subpath_exists(tmp_path):
    src = tmp_path / "snippets"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "util.py").write_text("# util")

    target = tmp_path / "myapp"
    target.mkdir()
    (target / ".git").mkdir()
    (target / "lib").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["infuse", "snippets", "--into", "myapp/lib"])
    assert result.exit_code != 0
    assert "already exists" in result.output


# --- delete ---


def test_delete_repo(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "file.txt").write_text("data")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok()
        result = runner.invoke(main, ["delete", "myrepo"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted myrepo locally" in result.output
    assert not repo.exists()
    # Should tag remote, not delete it
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("git tag jam-delete" in c for c in cmds)
    assert any("git push origin tag jam-delete" in c for c in cmds)
    assert not any("gh repo delete" in c for c in cmds)


def test_delete_aborted_on_confirm(tmp_path):
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / ".git").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["delete", "myrepo"], input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output
    assert repo.exists()


# --- undo ---


@patch("jam.helpers.clear_breadcrumb")
@patch("jam.helpers.load_breadcrumb", return_value={"action": "down", "pre_head": "abc12345"})
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_undo_down(mock_isdir, mock_run, mock_load, mock_clear):
    mock_run.side_effect = [ok()]  # git reset --hard
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code == 0
    assert "Undid down" in result.output
    assert "abc12345" in result.output
    mock_run.assert_any_call("git reset --hard abc12345", cwd="/tmp/dev/myrepo")
    mock_clear.assert_called_once()


@patch("jam.helpers.clear_breadcrumb")
@patch("jam.helpers.load_breadcrumb", return_value={"action": "up", "pre_head": "abc12345"})
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_undo_up(mock_isdir, mock_run, mock_load, mock_clear):
    mock_run.side_effect = [ok(), ok()]  # git reset, git push --force
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code == 0
    assert "Undid up" in result.output
    mock_run.assert_any_call("git push --force", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.clear_breadcrumb")
@patch("jam.helpers.load_breadcrumb", return_value={"action": "land", "pre_head": "abc12345"})
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_undo_land(mock_isdir, mock_run, mock_load, mock_clear):
    mock_run.side_effect = [ok(), ok()]  # git reset, git push --force
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code == 0
    assert "Undid land" in result.output
    mock_run.assert_any_call("git push --force", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.clear_breadcrumb")
@patch("jam.helpers.load_breadcrumb", return_value={"action": "infuse", "pre_head": "abc12345"})
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_undo_infuse(mock_isdir, mock_run, mock_load, mock_clear):
    mock_run.side_effect = [ok()]  # git reset --hard (no force push needed)
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code == 0
    assert "Undid infuse" in result.output
    mock_run.assert_any_call("git reset --hard abc12345", cwd="/tmp/dev/myrepo")
    mock_clear.assert_called_once()


@patch("jam.helpers.load_breadcrumb", return_value=None)
@patch("os.path.isdir", return_value=True)
def test_undo_nothing(mock_isdir, mock_load):
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code != 0
    assert "Nothing to undo" in (result.output + (result.stderr or ""))
