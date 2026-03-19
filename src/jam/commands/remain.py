import json
import os

import click

from jam import helpers

REMAIN_HOOK_COMMAND = (
    'if git rev-parse --verify master >/dev/null 2>&1'
    ' && git rev-parse --verify origin/main >/dev/null 2>&1'
    ' && ! git rev-parse --verify origin/master >/dev/null 2>&1;'
    ' then git branch -m master main && git branch -u origin/main main; fi'
)


def _add_remain_hook(repo_path):
    """Add the remain startup hook to a repo's .claude/settings.json.

    Returns True if the hook was added (or already present), False on error.
    """
    settings_path = os.path.join(repo_path, ".claude", "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)

    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)

    # Check if the hook is already present
    for event in settings.get("hooks", {}).get("SessionStart", []):
        for hook in event.get("hooks", []):
            if hook.get("command") == REMAIN_HOOK_COMMAND:
                return True  # already installed

    # Append the hook
    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])
    session_start.append({
        "hooks": [
            {
                "type": "command",
                "command": REMAIN_HOOK_COMMAND,
            }
        ]
    })

    ordered = {"$schema": "https://json.schemastore.org/claude-code-settings.json"}
    ordered.update(settings)
    with open(settings_path, "w") as f:
        json.dump(ordered, f, indent=2)
    return True


@click.command()
def remain():
    """Fix master/main branch confusion across all repos."""
    jam_home = helpers.get_jam_home()
    added = []
    skipped = []

    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            continue
        if _add_remain_hook(repo_path):
            added.append(entry)
        else:
            skipped.append(entry)

    click.echo(f"Added remain hook to {len(added)} repo{'s' if len(added) != 1 else ''}.")
    if skipped:
        click.echo(f"Skipped: {', '.join(skipped)}")
