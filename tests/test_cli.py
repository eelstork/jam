import os
from subprocess import CompletedProcess
from unittest.mock import call, mock_open, patch

from click.testing import CliRunner

from jam import helpers
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
@patch("builtins.open", mock_open())
@patch("os.path.exists", return_value=False)
def test_new_succeeds_when_gh_view_redirects(mock_exists, mock_run):
    """If the name was previously used and renamed on GitHub, `gh repo view`
    follows the redirect. jam must treat the original name as available."""
    mock_run.side_effect = [
        ok("testuser"),                                         # gh api user
        ok('{"nameWithOwner":"testuser/old-notes"}'),           # gh repo view (redirected)
        ok(),                                                   # gh repo create
        ok(), ok(), ok(), ok(),
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["new", "notes"])
    assert result.exit_code == 0, result.output
    assert "Created testuser/notes" in result.output


@patch("jam.helpers.run")
def test_new_fails_when_repo_exists(mock_run):
    mock_run.side_effect = [
        ok("testuser"),                                          # gh api user
        ok('{"nameWithOwner":"testuser/myrepo"}'),               # gh repo view (exists — bad)
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
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_up_with_name(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(stdout=" M file.txt"), ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    assert "Pushed" in result.output
    mock_run.assert_any_call("git status --porcelain", cwd="/tmp/dev/myrepo")
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")
    mock_run.assert_any_call('git commit -m "fix stuff"', cwd="/tmp/dev/myrepo")
    mock_crumb.assert_called_once_with("/tmp/dev/myrepo", "up", pre_head="abc1234")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_up_force_push(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(stdout=" M file.txt"), ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "--force", "myrepo", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git push --force", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=False)
@patch("os.getcwd", return_value="/tmp/dev/myrepo")
def test_up_without_name_uses_cwd(mock_cwd, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(stdout=" M file.txt"), ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "fix stuff"])
    assert result.exit_code == 0
    mock_run.assert_any_call("git add -A", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_up_no_changes_just_pushes(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(stdout=""), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "myrepo"])
    assert result.exit_code == 0
    assert "Pushed" in result.output
    calls = [str(c) for c in mock_run.call_args_list]
    assert not any("git add" in c for c in calls)
    assert not any("git commit" in c for c in calls)


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_up_prompts_for_message(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [ok(stdout=" M file.txt"), ok(), ok(), ok()]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "myrepo"], input="my commit msg\n")
    assert result.exit_code == 0
    assert "Pushed" in result.output
    mock_run.assert_any_call('git commit -m "my commit msg"', cwd="/tmp/dev/myrepo")


# --- push (pull-and-retry when the branch is behind) ---


@patch("jam.helpers.run")
def test_push_succeeds_without_pull(mock_run):
    mock_run.side_effect = [ok()]
    result = helpers.push("/repo")
    assert result.returncode == 0
    mock_run.assert_called_once_with("git push", cwd="/repo")


@patch("jam.helpers.run")
def test_push_passes_extra_args(mock_run):
    mock_run.side_effect = [ok()]
    helpers.push("/repo", "--force")
    mock_run.assert_called_once_with("git push --force", cwd="/repo")


@patch("jam.helpers.run")
def test_push_pulls_and_retries_when_behind(mock_run):
    rejected = err(
        "! [rejected]        main -> main (fetch first)\n"
        "error: failed to push some refs\n"
        "hint: Updates were rejected because the remote contains work that "
        "you do not have locally."
    )
    mock_run.side_effect = [rejected, ok(), ok()]
    result = helpers.push("/repo")
    assert result.returncode == 0
    assert mock_run.call_args_list == [
        call("git push", cwd="/repo"),
        call("git pull --no-rebase --no-edit", cwd="/repo"),
        call("git push", cwd="/repo"),
    ]


@patch("jam.helpers.run")
def test_push_non_fast_forward_also_triggers_pull(mock_run):
    mock_run.side_effect = [
        err("! [rejected] main -> main (non-fast-forward)"),
        ok(),
        ok(),
    ]
    result = helpers.push("/repo")
    assert result.returncode == 0
    mock_run.assert_any_call("git pull --no-rebase --no-edit", cwd="/repo")


@patch("jam.helpers.run")
def test_push_does_not_pull_on_unrelated_rejection(mock_run):
    # A protected branch / declined hook is "rejected" too, but pulling won't
    # help -- jam must surface it, not loop.
    mock_run.side_effect = [
        err(
            "remote: error: GH006: Protected branch update failed for "
            "refs/heads/main.\n ! [remote rejected] main -> main "
            "(protected branch hook declined)"
        )
    ]
    result = helpers.push("/repo")
    assert result.returncode == 1
    mock_run.assert_called_once_with("git push", cwd="/repo")


@patch("jam.helpers.run")
def test_push_returns_pull_failure_when_pull_conflicts(mock_run):
    mock_run.side_effect = [
        err("! [rejected] main -> main (non-fast-forward)"),
        err("CONFLICT (content): Merge conflict in f\nAutomatic merge failed"),
    ]
    result = helpers.push("/repo")
    assert result.returncode == 1
    assert "CONFLICT" in result.stderr
    # Only the first push was attempted; no retry after a failed pull.
    pushes = [c for c in mock_run.call_args_list if c == call("git push", cwd="/repo")]
    assert len(pushes) == 1


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_up_pulls_and_retries_when_behind(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(stdout=" M file.txt"),            # git status --porcelain
        ok(),                                # git add -A
        ok(),                                # git commit
        err("main -> main (fetch first)"),   # git push -> rejected (behind)
        ok(),                                # git pull --no-rebase --no-edit
        ok(),                                # git push (retry)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["up", "myrepo", "fix stuff"])
    assert result.exit_code == 0, result.output
    assert "Pushed" in result.output
    mock_run.assert_any_call("git pull --no-rebase --no-edit", cwd="/tmp/dev/myrepo")


# --- down ---


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_down_with_name(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
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
@patch("jam.helpers.is_repo", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_down_force(mock_isdir, mock_is_repo, mock_run, mock_head, mock_crumb):
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


@patch("jam.helpers.get_gh_user", return_value="testuser")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=False)
def test_down_delegates_to_clone_if_not_local(mock_is_repo, mock_run, mock_gh_user):
    mock_run.side_effect = [ok()]  # git clone
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "newrepo"])
    assert result.exit_code == 0
    assert "Cloned" in result.output
    mock_run.assert_any_call(
        "git clone https://github.com/testuser/newrepo.git /tmp/dev/newrepo"
    )


@patch("jam.helpers.get_gh_user", return_value="testuser")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=False)
def test_down_clone_fails_if_not_on_remote(mock_is_repo, mock_run, mock_gh_user):
    mock_run.side_effect = [CompletedProcess(args="", returncode=1, stdout="", stderr="not found")]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["down", "nonexistent"])
    assert result.exit_code != 0
    assert "Could not clone" in result.output


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


@patch("jam.helpers.get_gh_user", return_value="testuser")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=False)
def test_clone_from_remote(mock_is_repo, mock_run, mock_gh_user):
    mock_run.side_effect = [ok()]  # git clone
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "myrepo"])
    assert result.exit_code == 0
    assert "Cloned" in result.output
    mock_run.assert_any_call(
        "git clone https://github.com/testuser/myrepo.git /tmp/dev/myrepo"
    )


@patch("jam.helpers.get_gh_user", return_value="testuser")
@patch("jam.helpers.run")
@patch("jam.helpers.is_repo", return_value=False)
def test_clone_fails_if_not_on_remote(mock_is_repo, mock_run, mock_gh_user):
    mock_run.side_effect = [
        CompletedProcess(args="", returncode=1, stdout="", stderr="not found")
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "nonexistent"])
    assert result.exit_code != 0
    assert "Could not clone" in result.output


@patch("jam.helpers.is_repo", return_value=True)
def test_clone_fails_if_already_local(mock_is_repo):
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["clone", "existing"])
    assert result.exit_code != 0
    assert "already exists" in result.output


# --- land ---


BRANCHES_OUTPUT = "origin/feat-branch\norigin/main\n"
COMMITS_OUTPUT = "abc1234 first commit\ndef5678 second commit\nghi9012 third commit\njkl3456 fourth commit\n"


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_fast(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        ok(),                   # git push
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code == 0
    assert "Landed 4 commits from feat-branch" in result.output
    mock_crumb.assert_called_once_with("/tmp/dev/myrepo", "land", pre_head="abc1234")
    # land should NOT delete the branch (local or remote)
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert not any("branch -d" in c for c in cmds)
    assert not any("push origin --delete" in c for c in cmds)



@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_no_branches(mock_isdir, mock_run):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok("origin/main\n"),    # git for-each-ref (only main)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code == 0
    assert "No branches to land" in result.output


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_all_fast(mock_config, mock_run, mock_head, mock_crumb, tmp_path):
    # Set up two repos with .git dirs
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    # non-repo dir should be ignored
    (tmp_path / "notrepo").mkdir()

    mock_run.side_effect = [
        # alpha: _get_landable
        ok(),                                       # git fetch
        ok("[]"),                                   # gh pr list (no open PR)
        ok("origin/feat-a\norigin/main\n"),         # git for-each-ref
        ok("aaa1111 alpha change\n"),                # git log (1 commit)
        # beta: _get_landable
        ok(),                                       # git fetch
        ok("[]"),                                   # gh pr list (no open PR)
        ok("origin/feat-b\norigin/main\n"),         # git for-each-ref
        ok("bbb2222 beta first\nccc3333 beta second\n"),  # git log (2 commits)
        # alpha: _do_land
        ok(),                                       # git checkout main
        ok(),                                       # git merge
        ok(),                                       # git push
        # beta: _do_land
        ok(),                                       # git checkout main
        ok(),                                       # git merge
        ok(),                                       # git push
    ]
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["land", "--all"])
    assert result.exit_code == 0
    assert "Landed 1 commit from feat-a in alpha" in result.output
    assert "Landed 2 commits from feat-b in beta" in result.output
    assert "Landed 2 repos" in result.output



@patch("jam.helpers.run")
def test_land_all_no_repos(mock_run, tmp_path):
    (tmp_path / "empty" / ".git").mkdir(parents=True)

    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok("origin/main\n"),    # only main
    ]
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["land", "--all"])
    assert result.exit_code == 0
    assert "No repos with branches to land" in result.output


@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
def test_land_fetch_failure_shows_reason(mock_isdir, mock_run):
    mock_run.side_effect = [
        err("could not resolve host"),  # git fetch fails
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code != 0
    assert "fetch failed" in result.output


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_merge_failure_shows_reason(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        err("merge conflict"),  # git merge fails
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code != 0
    assert "merge failed" in result.output


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_push_failure_shows_reason(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        err("rejected"),        # git push fails
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code != 0
    assert "push failed" in result.output


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_pulls_and_retries_when_behind(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                                       # git fetch
        ok("[]"),                                   # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),                        # git for-each-ref
        ok(COMMITS_OUTPUT),                         # git log
        ok(),                                       # git checkout main
        ok(),                                       # git merge
        err("main -> main (non-fast-forward)"),     # git push -> rejected (behind)
        ok(),                                       # git pull --no-rebase --no-edit
        ok(),                                       # git push (retry)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "Landed 4 commits from feat-branch" in result.output
    mock_run.assert_any_call("git pull --no-rebase --no-edit", cwd="/tmp/dev/myrepo")


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_csv(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        # first repo (alpha)
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        ok(),                   # git push
        # second repo (beta)
        ok(),                   # git fetch
        ok("[]"),               # gh pr list (no open PR)
        ok(BRANCHES_OUTPUT),    # git for-each-ref
        ok(COMMITS_OUTPUT),     # git log
        ok(),                   # git checkout main
        ok(),                   # git merge
        ok(),                   # git push
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "alpha,", "beta"])
    assert result.exit_code == 0
    assert result.output.count("Landed 4 commits from feat-branch") == 2


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_prefers_open_pr(mock_config, mock_isdir, mock_run, mock_head, mock_crumb):
    mock_run.side_effect = [
        ok(),                                              # git fetch
        ok('[{"number": 42, "headRefName": "feat-branch", "title": "Add cool feature", "updatedAt": "2026-05-12T00:00:00Z"}]'),
        ok(COMMITS_OUTPUT),                                # git log on PR branch
        ok(),                                              # git checkout main
        ok(),                                              # gh pr merge
        ok(),                                              # git pull
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "Landed PR #42: Add cool feature" in result.output
    assert "feat-branch" in result.output
    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("gh pr merge 42" in c for c in cmds)
    # When a PR is open we should NOT consult the per-branch listing or run
    # a local merge -- the PR is the source of truth.
    assert not any("for-each-ref" in c for c in cmds)
    assert not any(c.startswith("git merge") for c in cmds)


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_open_pr_wins_over_newer_branch(
    mock_config, mock_isdir, mock_run, mock_head, mock_crumb,
):
    """If a PR is open on an older branch while a newer branch has no PR,
    the PR still wins.
    """
    mock_run.side_effect = [
        ok(),                                              # git fetch
        # An open PR on an older branch (not the most recently pushed).
        ok('[{"number": 5, "headRefName": "old-feature", "title": "Fix bug X", "updatedAt": "2026-05-10T00:00:00Z"}]'),
        ok("zzz0000 pr commit\n"),                         # git log on PR branch
        ok(),                                              # git checkout main
        ok(),                                              # gh pr merge
        ok(),                                              # git pull
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "Landed PR #5: Fix bug X" in result.output
    assert "old-feature" in result.output
    cmds = [c.args[0] for c in mock_run.call_args_list]
    # The newer branch must not be picked up: no for-each-ref consulted.
    assert not any("for-each-ref" in c for c in cmds)
    assert any("git log origin/main..origin/old-feature" in c for c in cmds)


@patch("jam.helpers.save_breadcrumb")
@patch("jam.helpers.get_head", return_value="abc1234")
@patch("jam.helpers.run")
@patch("os.path.isdir", return_value=True)
@patch("jam.helpers.get_jam_config", return_value=None)
def test_land_pr_merge_failure_shows_reason(
    mock_config, mock_isdir, mock_run, mock_head, mock_crumb,
):
    mock_run.side_effect = [
        ok(),                                              # git fetch
        ok('[{"number": 7, "headRefName": "feat-branch", "title": "T", "updatedAt": "2026-05-12T00:00:00Z"}]'),
        ok(COMMITS_OUTPUT),                                # git log on PR branch
        ok(),                                              # git checkout main
        err("not mergeable"),                              # gh pr merge fails
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["land", "myrepo"])
    assert result.exit_code != 0
    assert "PR merge failed" in result.output


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
    # Should not call any remote commands
    mock_run.assert_not_called()


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


@patch("jam.helpers.load_breadcrumb", return_value=None)
@patch("os.path.isdir", return_value=True)
def test_undo_nothing(mock_isdir, mock_load):
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["undo", "myrepo"])
    assert result.exit_code == 0
    assert "Nothing to undo" in result.output


# --- root ---


def test_root_from_env():
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["root"])
    assert result.exit_code == 0
    assert "/tmp/dev" in result.output


def test_root_from_config_file(tmp_path):
    config_dir = tmp_path / ".config" / "jam"
    config_dir.mkdir(parents=True)
    (config_dir / "root").write_text("/tmp/myrepos\n")
    with patch("jam.helpers.os.path.expanduser", return_value=str(tmp_path)):
        runner = CliRunner(env={})
        result = runner.invoke(main, ["root"])
    assert result.exit_code == 0
    assert "/tmp/myrepos" in result.output


def test_root_env_overrides_config(tmp_path):
    config_dir = tmp_path / ".config" / "jam"
    config_dir.mkdir(parents=True)
    (config_dir / "root").write_text("/tmp/from-file\n")
    with patch("jam.helpers.os.path.expanduser", return_value=str(tmp_path)):
        runner = CliRunner(env={"JAM_HOME": "/tmp/from-env"})
        result = runner.invoke(main, ["root"])
    assert result.exit_code == 0
    assert "/tmp/from-env" in result.output


def test_root_fails_without_anything():
    with patch("jam.helpers.os.path.expanduser", return_value="/nonexistent"):
        runner = CliRunner(env={})
        result = runner.invoke(main, ["root"])
    assert result.exit_code != 0
    assert "set-root" in (result.output + (result.stderr or ""))


# --- set-root ---


def test_set_root(tmp_path):
    config_dir = tmp_path / ".config" / "jam"
    target = tmp_path / "repos"
    target.mkdir()
    with patch("jam.helpers._config_dir", return_value=str(config_dir)):
        runner = CliRunner(env={})
        result = runner.invoke(main, ["set-root", str(target)])
    assert result.exit_code == 0
    assert "Jam root set to" in result.output
    assert (config_dir / "root").read_text().strip() == str(target)


def test_set_root_nonexistent_dir():
    runner = CliRunner(env={})
    result = runner.invoke(main, ["set-root", "/no/such/path"])
    assert result.exit_code != 0
    assert "does not exist" in (result.output + (result.stderr or ""))


# --- match_repo ---


def test_match_repo_exact(tmp_path):
    (tmp_path / "my-project").mkdir()
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    from jam.helpers import match_repo
    with patch.dict(os.environ, {"JAM_HOME": str(tmp_path)}):
        assert match_repo("my-project") == "my-project"


def test_match_repo_prefix(tmp_path):
    (tmp_path / "my-project").mkdir()
    with patch.dict(os.environ, {"JAM_HOME": str(tmp_path)}):
        from jam.helpers import match_repo
        assert match_repo("my-p") == "my-project"


def test_match_repo_ambiguous(tmp_path):
    (tmp_path / "my-project").mkdir()
    (tmp_path / "my-package").mkdir()
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    from jam.helpers import match_repo
    with patch.dict(os.environ, {"JAM_HOME": str(tmp_path)}):
        try:
            match_repo("my-p")
            assert False, "Should have failed"
        except SystemExit:
            pass  # helpers.fail calls sys.exit


def test_match_repo_not_found(tmp_path):
    (tmp_path / "other-repo").mkdir()
    from jam.helpers import match_repo
    with patch.dict(os.environ, {"JAM_HOME": str(tmp_path)}):
        try:
            match_repo("nope")
            assert False, "Should have failed"
        except SystemExit:
            pass


def test_delete_prefix_match(tmp_path):
    """jam delete with a prefix should resolve to the full repo name."""
    repo = tmp_path / "my-long-name"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "file.txt").write_text("data")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok()
        result = runner.invoke(main, ["delete", "my-l"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted my-long-name locally" in result.output
    assert not repo.exists()


def test_down_prefix_match(tmp_path):
    """jam down with a prefix should resolve to the full repo name."""
    repo = tmp_path / "my-long-name"
    repo.mkdir()
    (repo / ".git").mkdir()

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    with patch("jam.helpers.save_breadcrumb"), \
         patch("jam.helpers.get_head", return_value="abc1234"), \
         patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok()
        result = runner.invoke(main, ["down", "my-l"])
    assert result.exit_code == 0
    assert "Pulled" in result.output


# --- cooldown ---


def test_cooldown_shows_commits(tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)
    (tmp_path / "notrepo").mkdir()

    with patch("jam.helpers.run") as mock_run:
        mock_run.side_effect = [
            ok("abc1234 first commit\ndef5678 second commit"),  # alpha
            ok(""),                                              # beta (no commits)
        ]
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["cooldown"])
    assert result.exit_code == 0
    assert "alpha (2)" in result.output
    assert "first commit" in result.output
    assert "beta" not in result.output


def test_cooldown_no_commits(tmp_path):
    (tmp_path / "myrepo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok("")
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["cooldown"])
    assert result.exit_code == 0
    assert "No commits since 7 am" in result.output


# --- standup ---


def test_standup_shows_commits(tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok("abc1234 fix thing")
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["standup"])
    assert result.exit_code == 0
    assert "alpha (1)" in result.output
    assert "fix thing" in result.output
    # Verify the --since flag references yesterday
    since_arg = mock_run.call_args_list[0][0][0]
    assert "--since=" in since_arg


def test_standup_no_commits(tmp_path):
    (tmp_path / "myrepo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok("")
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["standup"])
    assert result.exit_code == 0
    assert "No commits since 7 am yesterday" in result.output


# --- retro ---


def test_retro_shows_commits(tmp_path):
    (tmp_path / "alpha" / ".git").mkdir(parents=True)
    (tmp_path / "beta" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.side_effect = [
            ok("aaa1111 monday work\nbbb2222 tuesday work"),
            ok("ccc3333 beta fix"),
        ]
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["retro"])
    assert result.exit_code == 0
    assert "alpha (2)" in result.output
    assert "beta (1)" in result.output


def test_retro_no_commits(tmp_path):
    (tmp_path / "myrepo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok("")
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["retro"])
    assert result.exit_code == 0
    assert "No commits in the past week" in result.output


def test_retro_cutoff_is_monday(tmp_path):
    """The retro cutoff should be a Monday at 7am, at least 7 days ago."""
    from datetime import datetime, timedelta

    today = datetime.now()
    week_ago = today - timedelta(days=7)
    expected_monday = week_ago - timedelta(days=week_ago.weekday())
    expected_since = expected_monday.replace(hour=7, minute=0, second=0).strftime("%Y-%m-%d %H:%M")

    (tmp_path / "repo" / ".git").mkdir(parents=True)

    with patch("jam.helpers.run") as mock_run:
        mock_run.return_value = ok("")
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        runner.invoke(main, ["retro"])
    since_arg = mock_run.call_args_list[0][0][0]
    assert expected_since in since_arg


# --- stats ---


def test_stats_shows_counts(tmp_path):
    log = tmp_path / "usage.log"
    log.write_text(
        "2026-03-15T10:00:00 up\n"
        "2026-03-15T10:01:00 up\n"
        "2026-03-15T10:02:00 down\n"
        "2026-03-15T10:03:00 up\n"
    )
    with patch("jam.helpers._usage_log_path", return_value=str(log)):
        runner = CliRunner()
        result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    # most used first
    assert "up" in lines[0]
    assert "3" in lines[0]
    assert "down" in lines[1]
    assert "1" in lines[1]


def test_stats_no_data(tmp_path):
    log = tmp_path / "usage.log"
    with patch("jam.helpers._usage_log_path", return_value=str(log)):
        runner = CliRunner()
        result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0
    assert "No usage data" in result.output


def test_stats_clear(tmp_path):
    log = tmp_path / "usage.log"
    log.write_text("2026-03-15T10:00:00 up\n")
    with patch("jam.helpers._usage_log_path", return_value=str(log)):
        runner = CliRunner()
        result = runner.invoke(main, ["stats", "--clear"])
    assert result.exit_code == 0
    assert "cleared" in result.output
    assert not log.exists()


# --- prune ---


def test_prune_finds_readme_only(tmp_path):
    """_is_readme_only returns True for a repo with only a README."""
    from jam.commands.prune import _is_readme_only

    repo = tmp_path / "empty-proj"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# hello\n")
    assert _is_readme_only(str(repo)) is True


def test_prune_detects_content(tmp_path):
    """_is_readme_only returns False when non-readme files exist."""
    from jam.commands.prune import _is_readme_only

    repo = tmp_path / "real-proj"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# hello\n")
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hi')\n")
    assert _is_readme_only(str(repo)) is False


def test_prune_detects_extra_markdown(tmp_path):
    """_is_readme_only returns False when extra .md files exist."""
    from jam.commands.prune import _is_readme_only

    repo = tmp_path / "docs-proj"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# hello\n")
    (repo / "notes.md").write_text("some notes\n")
    assert _is_readme_only(str(repo)) is False


def test_prune_ignores_dotfiles(tmp_path):
    """_is_readme_only ignores .gitignore and .claude/ files."""
    from jam.commands.prune import _is_readme_only

    repo = tmp_path / "dotfiles-proj"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# hello\n")
    (repo / ".gitignore").write_text("*.pyc\n")
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}\n")
    assert _is_readme_only(str(repo)) is True


def test_prune_find_readme_only_repos(tmp_path):
    """_find_readme_only_repos lists only readme-only repos from JAM_HOME."""
    from jam.commands.prune import _find_readme_only_repos

    # readme-only repo
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / ".git").mkdir()
    (empty / "README.md").write_text("# empty\n")

    # repo with real content
    real = tmp_path / "real"
    real.mkdir()
    (real / ".git").mkdir()
    (real / "README.md").write_text("# real\n")
    src = real / "src"
    src.mkdir()
    (src / "app.py").write_text("pass\n")

    with patch("jam.helpers.get_jam_home", return_value=str(tmp_path)):
        repos = _find_readme_only_repos()
    assert repos == ["empty"]



def test_prune_no_readme_only_repos(tmp_path):
    """prune prints a message when no readme-only repos are found."""
    repo = tmp_path / "real"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# real\n")
    src = repo / "src"
    src.mkdir()
    (src / "app.py").write_text("pass\n")

    with patch("jam.commands.prune.sys") as mock_sys:
        mock_sys.stdin.isatty.return_value = True
        mock_sys.platform = "linux"
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["prune"])
    assert result.exit_code == 0
    assert "No readme-only repos found" in result.output


# --- tree ---


@patch("jam.helpers.run")
def test_tree_default_depth(mock_run, tmp_path):
    """tree should show files up to depth 2 by default."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "README.md").write_text("# hello\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("pass\n")
    (repo / "src" / "lib").mkdir()
    (repo / "src" / "lib" / "utils.py").write_text("pass\n")

    # git check-ignore returns non-zero for non-ignored files
    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "myrepo" in result.output
    assert "README.md" in result.output
    assert "src" in result.output
    # depth 2: lib dir is shown (depth 1 inside src = depth 2 total)
    assert "lib" in result.output
    # depth 2: utils.py inside lib is depth 3, should NOT appear
    assert "utils.py" not in result.output


@patch("jam.helpers.run")
def test_tree_custom_depth(mock_run, tmp_path):
    """tree -L 1 should only show top-level entries."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "README.md").write_text("# hello\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("pass\n")

    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo", "-L", "1"])
    assert result.exit_code == 0, result.output
    assert "README.md" in result.output
    assert "src" in result.output
    # main.py is at depth 2, should not appear with -L 1
    assert "main.py" not in result.output


@patch("jam.helpers.run")
def test_tree_deep_depth(mock_run, tmp_path):
    """tree -L 4 should show deeply nested files."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / "lib").mkdir()
    (repo / "src" / "lib" / "utils.py").write_text("pass\n")

    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo", "-L", "4"])
    assert result.exit_code == 0, result.output
    assert "utils.py" in result.output


@patch("jam.helpers.run")
def test_tree_excludes_git_dir(mock_run, tmp_path):
    """tree should never show the .git directory."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (repo / "README.md").write_text("# hello\n")

    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo"])
    assert result.exit_code == 0, result.output
    assert ".git" not in result.output
    assert "HEAD" not in result.output


@patch("jam.helpers.run")
def test_tree_respects_gitignore(mock_run, tmp_path):
    """tree should hide files that git check-ignore says are ignored."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "README.md").write_text("# hello\n")
    (repo / "build").mkdir()
    (repo / "build" / "output.o").write_text("")

    def check_ignore_side_effect(cmd, **kwargs):
        if "build" in cmd:
            return CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        return CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    mock_run.side_effect = check_ignore_side_effect

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo"])
    assert result.exit_code == 0, result.output
    assert "README.md" in result.output
    assert "build" not in result.output


@patch("jam.helpers.run")
def test_tree_connectors(mock_run, tmp_path):
    """tree should use correct box-drawing connectors."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "aaa.txt").write_text("")
    (repo / "zzz.txt").write_text("")

    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo"])
    assert result.exit_code == 0, result.output
    # First item gets ├──, last item gets └──
    assert "├── aaa.txt" in result.output
    assert "└── zzz.txt" in result.output


@patch("jam.helpers.run")
def test_tree_empty_repo(mock_run, tmp_path):
    """tree on a repo with only .git should show just the repo name."""
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)

    mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["tree", "myrepo"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "myrepo"


# --- copy ---


@patch("jam.helpers.run")
def test_copy_with_as(mock_run, tmp_path):
    # Set up source repo
    src = tmp_path / "myrepo"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "README.md").write_text("# myrepo\n")
    (src / "src").mkdir()
    (src / "src" / "main.py").write_text("print('hi')\n")

    # gh repo create --clone creates the destination dir
    dst = tmp_path / "newrepo"

    def run_side_effect(cmd, **kwargs):
        if "gh repo create" in cmd:
            dst.mkdir()
            return ok()
        return ok()

    mock_run.side_effect = [
        ok("testuser"),  # gh api user
        err(),           # gh repo view (doesn't exist — good)
    ]

    # After the first two calls, switch to the dynamic side effect
    remaining = [
        ok(),            # gh repo create (handled by side effect)
        ok(),            # git checkout -b main
        ok(),            # git add
        ok(),            # git commit
        ok(),            # git push
    ]

    call_count = [0]
    original_side_effect = mock_run.side_effect

    def dynamic_side_effect(cmd, **kwargs):
        nonlocal call_count
        idx = call_count[0]
        call_count[0] += 1
        if idx < 2:
            return [ok("testuser"), err()][idx]
        if "gh repo create" in cmd:
            dst.mkdir()
            return ok()
        return ok()

    mock_run.side_effect = dynamic_side_effect

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["copy", "myrepo", "as", "newrepo"])
    assert result.exit_code == 0, result.output
    assert "Created testuser/newrepo from myrepo" in result.output
    # Verify files were copied
    assert (dst / "README.md").exists()
    assert (dst / "src" / "main.py").exists()
    # .git should NOT be copied from source
    assert not (dst / ".git" / "jam-undo.json").exists()


@patch("jam.helpers.run")
def test_copy_prompts_for_name(mock_run, tmp_path):
    src = tmp_path / "myrepo"
    src.mkdir()
    (src / ".git").mkdir()
    (src / "README.md").write_text("# myrepo\n")

    dst = tmp_path / "newrepo"

    call_count = [0]

    def dynamic_side_effect(cmd, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        if idx == 0:
            return ok("testuser")
        if idx == 1:
            return err()
        if "gh repo create" in cmd:
            dst.mkdir()
            return ok()
        return ok()

    mock_run.side_effect = dynamic_side_effect

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["copy", "myrepo"], input="newrepo\n")
    assert result.exit_code == 0, result.output
    assert "Created testuser/newrepo from myrepo" in result.output


@patch("jam.helpers.run")
@patch("jam.helpers.match_repo", return_value="myrepo")
def test_copy_fails_when_target_exists_on_github(mock_match, mock_run):
    mock_run.side_effect = [
        ok("testuser"),                                          # gh api user
        ok('{"nameWithOwner":"testuser/existing"}'),             # gh repo view (exists — bad)
    ]
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["copy", "myrepo", "as", "existing"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_copy_bad_filler_word():
    runner = CliRunner(env={"JAM_HOME": "/tmp/dev"})
    result = runner.invoke(main, ["copy", "myrepo", "to", "newrepo"])
    assert result.exit_code != 0
    assert "Expected 'as'" in result.output


def test_log_command_writes_to_log(tmp_path):
    log = tmp_path / "usage.log"
    with patch("jam.helpers._usage_log_path", return_value=str(log)):
        helpers.log_command("up")
        helpers.log_command("down")
    content = log.read_text()
    assert "up\n" in content
    assert "down\n" in content
    assert len(content.splitlines()) == 2
