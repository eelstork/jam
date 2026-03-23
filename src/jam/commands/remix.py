"""jam remix claude.md — itemize and share CLAUDE.md settings across repos."""

import json
import os
import sys

import click

from jam import helpers

KERYX_URL = "https://keryx.fly.dev"


def _find_claude_md_files(jam_home):
    """Find all CLAUDE.md files in repos under jam_home."""
    results = []
    try:
        entries = sorted(os.listdir(jam_home))
    except OSError:
        return results
    for name in entries:
        repo_path = os.path.join(jam_home, name)
        if not os.path.isdir(repo_path):
            continue
        claude_md = os.path.join(repo_path, "CLAUDE.md")
        if os.path.isfile(claude_md):
            results.append((name, claude_md))
    return results


def _parse_directives(text, repo_name):
    """Parse a CLAUDE.md into individual directives.

    Returns list of dicts: {text, repo, section}
    """
    directives = []
    current_section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            continue
        if stripped.startswith("# "):
            continue
        if stripped.startswith("- "):
            directives.append({
                "text": stripped[2:].strip(),
                "repo": repo_name,
                "section": current_section,
            })
        elif stripped and not stripped.startswith("#"):
            # Non-empty, non-heading, non-bullet line — treat as directive
            directives.append({
                "text": stripped,
                "repo": repo_name,
                "section": current_section,
            })
    return directives


def _ask_keryx(prompt, model="haiku"):
    """Send a question to keryx and return the response text."""
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({"text": prompt, "model": model}).encode()
        req = urllib.request.Request(
            f"{KERYX_URL}/ask",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode().strip()
    except Exception as e:
        return None


def _summarize_directives(directives):
    """Use keryx to generate terse summaries for each directive."""
    texts = "\n".join(
        f"{i+1}. [{d['repo']}] {d['text']}" for i, d in enumerate(directives)
    )
    prompt = (
        "For each numbered directive below, write a terse 3-6 word summary. "
        "Return ONLY a JSON array of strings, one summary per directive. "
        "Example: [\"sync e2e test docs\", \"report test costs\"]\n\n"
        f"{texts}"
    )
    result = _ask_keryx(prompt)
    if not result:
        # Fallback: truncate each directive
        return [d["text"][:50] for d in directives]
    try:
        # Find JSON array in the response
        start = result.index("[")
        end = result.rindex("]") + 1
        summaries = json.loads(result[start:end])
        if len(summaries) == len(directives):
            return summaries
    except (ValueError, json.JSONDecodeError):
        pass
    return [d["text"][:50] for d in directives]


def _deduplicate(directives, summaries):
    """Use keryx to detect duplicate directives. Returns deduplicated lists."""
    if len(directives) <= 1:
        return directives, summaries

    texts = "\n".join(
        f"{i+1}. {d['text']}" for i, d in enumerate(directives)
    )
    prompt = (
        "Below are numbered directives from CLAUDE.md files. "
        "Identify duplicates (same meaning, possibly different wording). "
        "Return ONLY a JSON array of integers — the 1-based indices to KEEP "
        "(drop duplicates, keeping the first occurrence). "
        "If no duplicates, return all indices.\n\n"
        f"{texts}"
    )
    result = _ask_keryx(prompt)
    if not result:
        return directives, summaries
    try:
        start = result.index("[")
        end = result.rindex("]") + 1
        keep_indices = json.loads(result[start:end])
        kept_d = [directives[i - 1] for i in keep_indices if 1 <= i <= len(directives)]
        kept_s = [summaries[i - 1] for i in keep_indices if 1 <= i <= len(summaries)]
        if kept_d:
            return kept_d, kept_s
    except (ValueError, json.JSONDecodeError):
        pass
    return directives, summaries


def _write_directive_to_claude_md(repo_path, directive):
    """Append a directive to a repo's CLAUDE.md, creating it if needed."""
    claude_md = os.path.join(repo_path, "CLAUDE.md")
    section = directive["section"]

    if os.path.isfile(claude_md):
        with open(claude_md) as f:
            content = f.read()
    else:
        content = "# CLAUDE.md\n"

    bullet = f"- {directive['text']}\n"

    # Check if already present
    if directive["text"] in content:
        return False

    if section:
        header = f"## {section}"
        if header in content:
            # Append under existing section
            idx = content.index(header) + len(header)
            # Find end of line
            nl = content.index("\n", idx)
            # Find next section or end
            next_section = content.find("\n## ", nl)
            if next_section == -1:
                insert_at = len(content)
            else:
                insert_at = next_section
            # Ensure newline before bullet
            if not content[insert_at - 1:insert_at] == "\n":
                bullet = "\n" + bullet
            content = content[:insert_at] + bullet + content[insert_at:]
        else:
            # Add new section
            content = content.rstrip("\n") + f"\n\n{header}\n\n{bullet}"
    else:
        content = content.rstrip("\n") + f"\n\n{bullet}"

    with open(claude_md, "w") as f:
        f.write(content)
    return True


def _share_to_repos(directive, jam_home, source_repo, target_repos):
    """Write a directive to one or more repos."""
    count = 0
    for repo_name in target_repos:
        if repo_name == source_repo:
            continue
        repo_path = os.path.join(jam_home, repo_name)
        if _write_directive_to_claude_md(repo_path, directive):
            click.echo(f"  Added to {repo_name}/CLAUDE.md")
            count += 1
        else:
            click.echo(f"  Already in {repo_name}/CLAUDE.md")
    return count


@click.command("remix")
@click.argument("target", default="claude.md")
def remix(target):
    """Itemize and share CLAUDE.md settings across repos."""
    if target.lower() != "claude.md":
        helpers.fail("Only 'claude.md' is supported right now.")

    jam_home = helpers.get_jam_home()

    # Step 1: Find all CLAUDE.md files
    found = _find_claude_md_files(jam_home)
    if not found:
        helpers.fail("No CLAUDE.md files found in any repo.")

    click.echo(f"Found CLAUDE.md in {len(found)} repo(s): {', '.join(r for r, _ in found)}")

    # Step 2: Parse directives
    all_directives = []
    for repo_name, path in found:
        with open(path) as f:
            text = f.read()
        all_directives.extend(_parse_directives(text, repo_name))

    if not all_directives:
        helpers.fail("No directives found in any CLAUDE.md.")

    # Step 3: Summarize via keryx
    click.echo("Summarizing directives...")
    summaries = _summarize_directives(all_directives)

    # Step 4: Deduplicate via keryx
    all_directives, summaries = _deduplicate(all_directives, summaries)
    click.echo(f"{len(all_directives)} unique directive(s) found.\n")

    if not sys.stdin.isatty():
        # Non-interactive: just list them
        for i, (d, s) in enumerate(zip(all_directives, summaries)):
            click.echo(f"  [{d['repo']}] {s}")
        return

    # Step 5: Interactive picker
    from jam.interactive import pick

    while True:
        items = [
            (s, f"[{d['repo']}] {d['section']}" if d["section"] else f"[{d['repo']}]")
            for d, s in zip(all_directives, summaries)
        ]
        idx = pick(items, header="remix claude.md — select a directive")
        if idx is None:
            return

        directive = all_directives[idx]
        click.echo(f"\n{directive['text']}")
        if directive["section"]:
            click.echo(f"  Section: {directive['section']}")
        click.echo(f"  Source:  {directive['repo']}")

        # Step 6: Share menu
        share_items = [
            ("Share to all repos", "Add this directive to every repo's CLAUDE.md"),
            ("Share to one repo", "Pick a single target repo"),
            ("Cancel", "Return to directive list"),
        ]
        action = pick(share_items, header="share")
        if action is None or action == 2:
            click.echo()
            continue

        # Get list of all repos
        try:
            all_repos = sorted(
                d for d in os.listdir(jam_home)
                if os.path.isdir(os.path.join(jam_home, d))
            )
        except OSError:
            all_repos = []

        if action == 0:
            # Share to all
            _share_to_repos(directive, jam_home, directive["repo"], all_repos)
            click.echo()
        elif action == 1:
            # Pick a target repo
            targets = [r for r in all_repos if r != directive["repo"]]
            if not targets:
                click.echo("No other repos to share to.\n")
                continue
            repo_items = [(r, "") for r in targets]
            ridx = pick(repo_items, header="select target repo")
            if ridx is not None:
                _share_to_repos(directive, jam_home, directive["repo"], [targets[ridx]])
            click.echo()
