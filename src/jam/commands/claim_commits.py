"""jam claim-commits — Set up commit attribution."""

import click

from jam import helpers


@click.command("claim-commits")
def claim_commits():
    """Set up commit attribution."""

    # Step 1: Restore personal attribution?
    choice = click.prompt(
        "Restore personal attribution? Removes \"Claude\" from AI-assisted "
        "commits and is only relevant to Claude Code users; AI assisted "
        "commits remain traceable",
        type=click.Choice(["yes", "no"], case_sensitive=False),
    )

    if choice == "no":
        click.echo("Attribution not enabled.")
        helpers.save_jam_config(claim_commits_done=True, attribution_enabled=False)
        return

    # Step 2: Write .claude/settings.json into the current repo (if in one)
    repo_root = helpers.git_repo_root()
    if repo_root:
        path = helpers.write_repo_claude_settings(repo_root)
        click.echo(f"Wrote {path}")
    click.echo("Personal attribution restored.")

    helpers.save_jam_config(attribution_enabled=True, claim_commits_done=True)

    click.echo("Done. You can now run 'jam reclaim' to reclaim commits.")
