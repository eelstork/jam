import click

from jam import helpers


@click.command()
@click.argument("name", default="")
@click.option("--all", "show_all", is_flag=True, help="Show all commits.")
@click.option("--fast", is_flag=True, help="Land without confirmation.")
def land(name, show_all, fast):
    """Merge the latest branch into main."""
    repo_path = helpers.resolve_repo(name or None)

    result = helpers.run("git fetch --all", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git fetch failed: {result.stderr.strip()}")

    result = helpers.run(
        "git for-each-ref --sort=-committerdate refs/remotes/origin/ "
        "--format=%(refname:short)",
        cwd=repo_path,
    )
    if result.returncode != 0:
        helpers.fail(f"Failed to list branches: {result.stderr.strip()}")

    branches = [
        b.strip() for b in result.stdout.strip().splitlines()
        if b.strip() and b.strip() not in ("origin/main", "origin/HEAD")
    ]
    if not branches:
        helpers.fail("No branches to land.")

    branch = branches[0]
    local_branch = branch.replace("origin/", "", 1)

    result = helpers.run(
        f"git log origin/main..{branch} --oneline",
        cwd=repo_path,
    )
    if result.returncode != 0:
        helpers.fail(f"Failed to get commits: {result.stderr.strip()}")

    commits = result.stdout.strip().splitlines()
    if not commits:
        helpers.fail(f"No new commits on {branch}.")

    n = len(commits)

    if fast:
        pass
    else:
        click.echo(f"Landing {branch} ({n} commit{'s' if n != 1 else ''}):")
        click.echo()
        display = commits if show_all else commits[:3]
        for c in display:
            click.echo(f"  {c}")
        if not show_all and n > 3:
            click.echo(f"  ... and {n - 3} more")
        click.echo()
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            return

    helpers.run("git checkout main", cwd=repo_path)
    result = helpers.run(f"git merge {branch}", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"Merge failed: {result.stderr.strip()}")

    result = helpers.run("git push", cwd=repo_path)
    if result.returncode != 0:
        helpers.fail(f"git push failed: {result.stderr.strip()}")

    helpers.run(f"git branch -d {local_branch}", cwd=repo_path)
    helpers.run(f"git push origin --delete {local_branch}", cwd=repo_path)

    click.echo(f"Landed {n} commit{'s' if n != 1 else ''} from {local_branch}.")
