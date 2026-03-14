"""jam claim-commits — Set up commit attribution and velocity tracking."""

import click

from jam import helpers
from jam import velocity


@click.command("claim-commits")
def claim_commits():
    """Set up commit attribution and velocity tracking."""

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

    helpers.save_jam_config(attribution_enabled=True)

    # Step 3: Measure velocity?
    click.echo()
    choice = click.prompt(
        "Assisted coding velocity (accel factor) may be displayed in your "
        "commit comments; to enable this feature, jam will establish an "
        "intrinsic vs assisted velocity baseline. This process requires "
        "scanning your github repos (read-only; skips repositories over "
        "25mb), and may take a few minutes",
        type=click.Choice(["yes", "no"], case_sensitive=False),
    )

    if choice == "no":
        helpers.save_jam_config(claim_commits_done=True)
        click.echo("Done. Run 'jam claim-commits' again to set up velocity later.")
        return

    username, token = velocity.resolve_github_credentials()
    if not username:
        helpers.fail("Could not resolve GitHub username. Is gh authenticated?")

    click.echo(f"\nScanning repos for {username} ...\n")

    def on_progress(event, **kw):
        if event == "repo_count":
            click.echo(f"Found {kw['count']} repo(s).")
        elif event == "repo_clone":
            click.echo(f"  {kw['name']:30s}  {kw['size_kb']:>8,} KB", nl=False)
        elif event == "repo_velocity":
            click.echo(f"  → {kw['velocity']:.1f} l/h")
        elif event == "repo_empty":
            click.echo(f"  → skipped")
        elif event == "repo_skip":
            click.echo(f"  {kw['name']:30s}  (skipped: {kw['reason']})")

    # Classic mode (human baseline)
    click.echo("Measuring classic (human) velocity ...")
    classic = velocity.aggregate_velocity(
        username, token, max_velocity=velocity.INTRINSIC_MAX_VELOCITY,
        exclude_author=velocity.EXCLUDE_BOTS,
        on_progress=on_progress,
    )

    # Machine-assisted mode
    click.echo("\nMeasuring machine-assisted velocity ...")
    machine = velocity.aggregate_velocity(
        username, token, max_velocity=velocity.MACHINE_MAX_VELOCITY,
        exclude_author=velocity.EXCLUDE_BOTS,
        on_progress=on_progress,
    )

    if classic and machine and classic > 0:
        multiplier = machine / classic
        click.echo(f"\nClassic velocity:  {classic:.1f} l/h")
        click.echo(f"Machine velocity:  {machine:.1f} l/h")
        click.echo(f"Multiplier:        x{multiplier:.1f}")

        helpers.save_jam_config(
            baseline_velocity=classic,
            machine_velocity=machine,
            multiplier=round(multiplier, 1),
        )
    else:
        click.echo("\nCould not compute velocity (insufficient data).")
        helpers.save_jam_config(claim_commits_done=True)
        return

    # Step 4: Display velocity tag on land?
    click.echo()
    choice = click.prompt(
        "Amend commit messages using velocity tag when landing branches?",
        type=click.Choice(["yes", "no"], case_sensitive=False),
    )

    helpers.save_jam_config(
        claim_commits_done=True,
        show_velocity_tag=(choice == "yes"),
    )

    click.echo("Done.")
