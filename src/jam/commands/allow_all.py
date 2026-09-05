import json
import os

import click

from jam import helpers

SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"

# Tool-level rules: a bare tool name allows every call to that tool.
# Bash covers every shell command, the file tools cover the whole repo,
# and the web/agent/skill tools stop asking for confirmation.
ALLOW_ALL_RULES = [
    "Bash",
    "Read",
    "Edit",
    "Write",
    "MultiEdit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "WebSearch",
    "Task",
    "Agent",
    "Skill",
    "TodoWrite",
    "TodoRead",
]


def _settings_path(repo_path):
    return os.path.join(repo_path, ".claude", "settings.json")


def _load_settings(repo_path):
    path = _settings_path(repo_path)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _save_settings(repo_path, settings):
    path = _settings_path(repo_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ordered = {"$schema": SCHEMA_URL}
    ordered.update(settings)
    with open(path, "w") as f:
        json.dump(ordered, f, indent=2)


def _is_clean(repo_path):
    """Return True if the repo has no staged or unstaged changes."""
    staged = helpers.run("git diff --cached --quiet", cwd=repo_path)
    unstaged = helpers.run("git diff --quiet", cwd=repo_path)
    return staged.returncode == 0 and unstaged.returncode == 0


def _has_rules(repo_path):
    """Return True if every allow-all rule is already present."""
    allow = _load_settings(repo_path).get("permissions", {}).get("allow", [])
    return all(rule in allow for rule in ALLOW_ALL_RULES)


def _add_rules(repo_path):
    """Merge the allow-all rules into a repo's permissions.allow list."""
    settings = _load_settings(repo_path)
    permissions = settings.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])
    for rule in ALLOW_ALL_RULES:
        if rule not in allow:
            allow.append(rule)
    _save_settings(repo_path, settings)


def _remove_rules(repo_path):
    """Strip the allow-all rules, leaving any other allow entries intact."""
    settings = _load_settings(repo_path)
    permissions = settings.get("permissions", {})
    allow = [r for r in permissions.get("allow", []) if r not in ALLOW_ALL_RULES]
    if allow:
        permissions["allow"] = allow
    else:
        permissions.pop("allow", None)
    if not permissions:
        settings.pop("permissions", None)
    _save_settings(repo_path, settings)


@click.command("allow-all")
@click.option("--unset", is_flag=True, help="Remove the allow-all rules from all repos.")
def allow_all(unset):
    """Grant Claude Code broad tool permissions across all repos."""
    jam_home = helpers.get_jam_home()

    repos = []
    for entry in sorted(os.listdir(jam_home)):
        repo_path = os.path.join(jam_home, entry)
        if os.path.isdir(os.path.join(repo_path, ".git")):
            repos.append((entry, repo_path))

    # Classify: needs work vs already done.
    # For --unset, "needs work" means has the rules; for set, means lacks them.
    done = []
    todo = []
    dirty = []
    for entry, repo_path in repos:
        click.echo(".", nl=False)
        has = _has_rules(repo_path)
        needs_work = has if unset else not has
        if not needs_work:
            done.append(entry)
        elif _is_clean(repo_path):
            todo.append(entry)
        else:
            dirty.append(entry)

    if repos:
        click.echo()  # newline after dots

    if dirty:
        click.echo(
            f"Aborted: {', '.join(dirty)} "
            f"{'has' if len(dirty) == 1 else 'have'} uncommitted changes. "
            "Please commit or stash first."
        )
        raise SystemExit(1)

    action = "remove" if unset else "add"
    modify = _remove_rules if unset else _add_rules
    for entry, repo_path in repos:
        if entry in done:
            continue
        modify(repo_path)
        settings_rel = os.path.join(".claude", "settings.json")
        helpers.run(f"git add {settings_rel}", cwd=repo_path)
        helpers.run(f'git commit -m "{action} allow-all permissions"', cwd=repo_path)
        helpers.run("git push", cwd=repo_path)

    verb = "Removed" if unset else "Added"
    prep = "from" if unset else "to"
    click.echo(
        f"{verb} allow-all permissions {prep} {len(todo)} "
        f"repo{'s' if len(todo) != 1 else ''}."
    )
    if done:
        label = "Already removed" if unset else "Already installed"
        click.echo(f"{label}: {', '.join(done)}")
