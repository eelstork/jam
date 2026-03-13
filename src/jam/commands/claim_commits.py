"""jam claim-commits — Set up commit attribution and velocity tracking."""

import click

from jam import helpers
from jam import velocity


@click.command("claim-commits")
def claim_commits():
    """Set up commit attribution and velocity tracking."""

    # Step 1: Enable attribution?
    choice = click.prompt(
        "Enable attribution? This restores your name on AI-assisted commits "
        "and is only relevant to Claude Code users",
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
        click.echo("Claude Code commit attribution suppressed in this repo.")
    else:
        click.echo("Not in a git repo — attribution will be applied on jam new/clone/land.")

    helpers.save_jam_config(attribution_enabled=True)

    # Step 3: Measure velocity?
    click.echo()
    measure = click.confirm(
        "Measure your coding velocity? This scans your GitHub repos (read-only) "
        "and takes a few minutes",
        default=False,
    )

    if not measure:
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
        username, token, max_velocity=100,
        exclude_author="bot,dependabot,renovate",
        on_progress=on_progress,
    )

    # Machine-assisted mode
    click.echo("\nMeasuring machine-assisted velocity ...")
    machine = velocity.aggregate_velocity(
        username, token, max_velocity=10000,
        exclude_author="bot,dependabot,renovate",
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
    show_tag = click.confirm(
        f"Display velocity tag [x{multiplier:.1f}] when landing branches?",
        default=True,
    )

    helpers.save_jam_config(
        claim_commits_done=True,
        show_velocity_tag=show_tag,
    )

    click.echo("Done.")
