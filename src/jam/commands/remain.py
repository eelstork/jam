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


def _is_clean(repo_path):
    """Return True if the repo has no staged or unstaged changes."""
    staged = helpers.run("git diff --cached --quiet", cwd=repo_path)
    unstaged = helpers.run("git diff --quiet", cwd=repo_path)
    return staged.returncode == 0 and unstaged.returncode == 0


def _has_hook(repo_path):
    """Return True if the remain hook is already installed."""
    settings_path = os.path.join(repo_path, ".claude", "settings.json")
    if not os.path.exists(settings_path):
        return False
    with open(settings_path) as f:
        settings = json.load(f)
    for event in settings.get("hooks", {}).get("SessionStart", []):
        for hook in event.get("hooks", []):
            if hook.get("command") == REMAIN_HOOK_COMMAND:
                return True
    return False


def _add_remain_hook(repo_path):
    """Add the remain startup hook to a repo's .claude/settings.json."""
    settings_path = os.path.join(repo_path, ".claude", "settings.json")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)

    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)

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


def _remove_remain_hook(repo_path):
    """Remove the remain startup hook from a repo's .claude/settings.json."""
    settings_path = os.path.join(repo_path, ".claude", "settings.json")
    with open(settings_path) as f:
        settings = json.load(f)

    session_start = settings.get("hooks", {}).get("SessionStart", [])
    settings["hooks"]["SessionStart"] = [
        event for event in session_start
        if not any(
            h.get("command") == REMAIN_HOOK_COMMAND
            for h in event.get("hooks", [])
        )
    ]

    # Clean up empty SessionStart / hooks
    if not settings["hooks"]["SessionStart"]:
        del settings["hooks"]["SessionStart"]
    if not settings["hooks"]:
        del settings["hooks"]

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)


@click.command()
@click.option("--unset", is_flag=True, help="Remove the remain hook from all repos.")
def remain(unset):
    """Fix master/main branch confusion across all repos."""
    jam_home = helpers.get_jam_home()

    # Discover repos
    repos = []
    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if os.path.isdir(os.path.join(repo_path, ".git")):
            repos.append((entry, repo_path))

    # Classify: needs work vs already done.
    # For --unset, "needs work" means has the hook; for set, means lacks it.
    done = []
    todo = []
    dirty = []
    for entry, repo_path in repos:
        click.echo(".", nl=False)
        has = _has_hook(repo_path)
        needs_work = has if unset else not has
        if not needs_work:
            done.append(entry)
        elif _is_clean(repo_path):
            todo.append(entry)
        else:
            dirty.append(entry)

    if repos:
        click.echo()  # newline after dots

    # Bail if any repo that needs work is dirty
    if dirty:
        click.echo(
            f"Aborted: {', '.join(dirty)} "
            f"{'has' if len(dirty) == 1 else 'have'} uncommitted changes. "
            "Please commit or stash first."
        )
        raise SystemExit(1)

    # Apply changes and commit/push
    action = "remove" if unset else "add"
    modify = _remove_remain_hook if unset else _add_remain_hook
    for entry, repo_path in repos:
        if entry in done:
            continue
        modify(repo_path)
        settings_rel = os.path.join(".claude", "settings.json")
        helpers.run(f"git add {settings_rel}", cwd=repo_path)
        helpers.run(f'git commit -m "{action} remain hook"', cwd=repo_path)
        helpers.run("git push", cwd=repo_path)

    verb = "Removed" if unset else "Added"
    prep = "from" if unset else "to"
    click.echo(
        f"{verb} remain hook {prep} {len(todo)} "
        f"repo{'s' if len(todo) != 1 else ''}."
    )
    if done:
        label = "Already removed" if unset else "Already installed"
        click.echo(f"{label}: {', '.join(done)}")
