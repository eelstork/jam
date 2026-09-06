import json
import os

import click

from jam import helpers

SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"
SETTINGS_REL = os.path.join(".claude", "settings.json")

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
    return os.path.join(repo_path, SETTINGS_REL)


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


def _reason(result):
    """One line explaining a failed git command.

    Prefer what the server said (``remote:`` lines, minus hints), then the
    first ``fatal:``/``error:`` line, then whatever git printed last.
    """
    lines = [l.strip() for l in (result.stderr + "\n" + result.stdout).splitlines()]
    lines = [l for l in lines if l]
    remote = [l[len("remote:"):].strip() for l in lines if l.startswith("remote:")]
    remote = [l for l in remote if l and not l.lower().startswith("hint")]
    if remote:
        return remote[0]
    for l in lines:
        if l.startswith(("fatal:", "error:")):
            return l
    return lines[-1] if lines else f"exit {result.returncode}"


def _current_branch(repo_path):
    result = helpers.run("git branch --show-current", cwd=repo_path)
    return result.stdout.strip() if result.returncode == 0 else ""


def _settings_dirty(repo_path):
    """True if .claude/settings.json has staged or unstaged changes."""
    result = helpers.run(f"git status --porcelain -- {SETTINGS_REL}", cwd=repo_path)
    return bool(result.stdout.strip())


def _unpushed_count(repo_path):
    """Commits ahead of upstream, or None if there is no upstream."""
    result = helpers.run("git rev-list --count @{u}..HEAD", cwd=repo_path)
    if result.returncode != 0:
        return None
    return int(result.stdout.strip() or 0)


def _apply(repo_path, unset):
    """Run the workflow on one repo. Returns (status, detail).

    status is "done" (nothing to do), "ok" (changed and pushed), or
    "skip" (left untouched; detail says why).
    """
    has = _has_rules(repo_path)
    needs_work = has if unset else not has
    if not needs_work:
        return "done", ""

    branch = _current_branch(repo_path)
    if branch != "main":
        return "skip", f"on branch {branch or '(detached)'}, not main"

    if _settings_dirty(repo_path):
        return "skip", f"{SETTINGS_REL} has uncommitted changes"

    pull = helpers.run("git pull --ff-only", cwd=repo_path)
    if pull.returncode != 0:
        return "skip", f"pull failed: {_reason(pull)}"

    ahead = _unpushed_count(repo_path)
    if ahead is None:
        return "skip", "no upstream branch"
    if ahead:
        return "skip", f"{ahead} unpushed commit{'s' if ahead != 1 else ''}, push those first"

    (_remove_rules if unset else _add_rules)(repo_path)
    action = "remove" if unset else "add"
    helpers.run(f"git add {SETTINGS_REL}", cwd=repo_path)
    commit = helpers.run(f'git commit -m "{action} allow-all permissions"', cwd=repo_path)
    if commit.returncode != 0:
        return "skip", f"commit failed: {_reason(commit)}"

    push = helpers.push(repo_path)
    if push.returncode != 0:
        return "skip", f"push failed (commit is local): {_reason(push)}"

    return "ok", ""


@click.command("allow-all")
@click.argument("name", required=False)
@click.option("--unset", is_flag=True, help="Remove the allow-all rules instead.")
def allow_all(name, unset):
    """Grant Claude Code broad tool permissions across all repos.

    With NAME, only that repo is processed (prefix matching applies).
    """
    jam_home = helpers.get_jam_home()

    if name:
        name = helpers.match_repo(name)
        repo_path = os.path.join(jam_home, name)
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            helpers.fail(f"{name} is not a git repo.")
        repos = [(name, repo_path)]
    else:
        repos = []
        for entry in sorted(os.listdir(jam_home)):
            repo_path = os.path.join(jam_home, entry)
            if os.path.isdir(os.path.join(repo_path, ".git")):
                repos.append((entry, repo_path))

    verb = "Removed" if unset else "Added"
    done = []
    changed = []
    skipped = []
    for entry, repo_path in repos:
        status, detail = _apply(repo_path, unset)
        if status == "done":
            done.append(entry)
        elif status == "ok":
            changed.append(entry)
            click.echo(f"{entry}: {verb.lower()}")
        else:
            skipped.append(entry)
            click.echo(f"{entry}: skipped, {detail}")

    prep = "from" if unset else "to"
    click.echo(
        f"{verb} allow-all permissions {prep} {len(changed)} "
        f"repo{'s' if len(changed) != 1 else ''}."
    )
    if done:
        label = "Already removed" if unset else "Already installed"
        click.echo(f"{label}: {', '.join(done)}")
    if skipped:
        click.echo(f"Skipped: {', '.join(skipped)}")
