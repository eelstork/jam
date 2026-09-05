# Jam 🍯

```
pip install git+https://github.com/eelstork/jam.git
```
Done with jam?
```
pip uninstall jam 
```

Developer mode: `pip install -e .` or `python install.py` after clone.

Opinionated cross platform Git wrapper written mainly for Claude Code (CC) users; not intended for team use.

I use `jam land REPO` every day; skips the ritualistic git flow that doesn't work when constantly
switching project and mainly retesting features; no need to create a branch in CC web UI. 

I do not know how you would benefit or not when using CC in the terminal; I like the web-UI because this provides a clean nix based dev env; then I retest (and test GUIs) on my local, providing a less pristine, bumpier (Windows based) environment.

`reclaim` (remove CC ads), `retro`, `standup` and `cooldown` (track weekly/daily work) are other commands I do enjoy.

Jam keeps all your repos under one roof (`JAM_HOME`) and talks to GitHub via `gh`. No config files, no boilerplate. The stuff you actually do, made fast.

Requires Python 3.10+, [git](https://git-scm.com), and [gh](https://cli.github.com) (authenticated).
If you're a github user, of course you already have them installed. Note: I do not believe jam a substitute for knowing and understanding git.

In the doc: 🔺local/remote changes; 🔷local changes only; 🟡informative or config command

## Setup

Point jam at your repos directory:

```
jam set-root ~/dev
```

Or set the `JAM_HOME` environment variable if you prefer.

## Commands

| | |
|---|---|
| 🔺`jam new NAME ["DESCRIPTION"]` | Spin up a repo on GitHub, clone it locally, push a readme. `--public` to make it public. Alias: `jam create`. [new.py](src/jam/commands/new.py) |
| 🔺`jam copy REPO as NEW` | Copy a repo as a new repo on GitHub. Creates a new private repo, copies all files (minus `.git/`), commits and pushes. Also: `jam copy REPO` prompts for the new name interactively. [copy.py](src/jam/commands/copy.py) |
| 🔺`jam rename REPO` | Rename a repo locally and on GitHub. Prompts for the new name. Refuses (without contacting GitHub) if the repo isn't local or if `origin` points at a different name than the local directory. [rename.py](src/jam/commands/rename.py) |
| 🔷`jam clone NAME` | Clone a repo from your GitHub account into the local jam root. Useful when a repo exists on GitHub but not locally. Also invoked automatically by `jam down NAME` when the repo isn't found locally. [clone.py](src/jam/commands/clone.py) |
| 🟡`jam list` | See what you've got. `--info` pulls the first line from each readme. [list.py](src/jam/commands/list.py) |
| 🔺`jam up "MESSAGE"` | Add everything, commit, push. One shot. `--name REPO` to target a specific repo, `--force` if you need it. If the push is rejected because the branch is behind the remote, jam pulls and retries once. [up.py](src/jam/commands/up.py) |
| 🔷`jam down [NAME]` | Pull latest. If the repo isn't local, delegates to `jam clone`. `--force` throws away local changes first. [down.py](src/jam/commands/down.py) |
| 🔺`jam land [NAME]` | Merge the most recent branch into main and show all landed commits. `--all` lands across all repos at once. If the push is rejected because main is behind the remote, jam pulls and retries once. [land.py](src/jam/commands/land.py) |
| 🔷`jam undo [NAME]` | Reverse the last jam command on a repo. Works with `up`, `down`, and `land`. [undo.py](src/jam/commands/undo.py) |
| 🔷`jam delete NAME` | Remove a repo locally. Tags the remote for later cleanup. Re-clone from GitHub to recover. [delete.py](src/jam/commands/delete.py) |
| 🔷`jam prune` | Interactively select and delete repos that only contain a README. Scans jam home, multi-select with arrow keys and x, removes local copies. [prune.py](src/jam/commands/prune.py) |
| 🔷`jam edit FILENAME [REPO]` | Open a file in its default application. If no repo is given, searches all repos. If multiple matches are found, pick interactively. [edit.py](src/jam/commands/edit.py) |
| 🟡`jam tree [NAME] [-L N]` | Show a `.gitignore`-aware directory tree for a repo. Defaults to depth 2, configurable with `-L` (matching Unix `tree` convention). [tree.py](src/jam/commands/tree.py) |
| 🔺`jam remain` | Fix master/main branch confusion across all repos. Installs a Claude Code `SessionStart` hook that auto-renames local `master` to `main` when the remote only has `main`. `--unset` removes the hook. Skips repos with uncommitted changes. [remain.py](src/jam/commands/remain.py) |
| 🟡`jam remix` | Itemize and share `CLAUDE.md` settings across repos. Parses directives from every repo's `CLAUDE.md`, summarizes and deduplicates them, then lets you interactively share directives to other repos. Non-interactive mode lists all unique directives. [remix.py](src/jam/commands/remix.py) |
| 🟡`jam cooldown` | List today's commits (since 7 am) per repo. Quick end-of-day recap. [cooldown.py](src/jam/commands/cooldown.py) |
| 🟡`jam stats` | Show command usage counts, most used first. Every command invocation is logged locally to `~/.config/jam/usage.log`. `--clear` discards the log. [stats.py](src/jam/commands/stats.py) |
| 🟡`jam root` | Print the current jam root directory. [root.py](src/jam/commands/root.py) |
| 🟡`jam set-root PATH` | Set the jam root directory. Writes to `~/.config/jam/root`. The `JAM_HOME` env var takes priority if set. [set_root.py](src/jam/commands/set_root.py) |
| 🟡`jam update` | Pull the latest jam source and reinstall. Runs `git pull` + `pip install -e .` from wherever jam is installed. [update.py](src/jam/commands/update.py) |

## Prefix matching

Repo names can be abbreviated. If the prefix is unambiguous, jam resolves it automatically — `jam up -n my-p` works if `my-project` is the only repo starting with `my-p`. Ambiguous prefixes show matching candidates.

## Command passthrough

Any command that isn't built-in gets routed to a script at the repo root. Drop a `deploy.sh`, `test.py`, or `build.ps1` next to your `.git` and run it with `jam deploy`, `jam test`, `jam build`. Extra arguments are forwarded: `jam build --release v2` runs `bash build.sh --release v2`.

Target a specific repo with `jam deploy myrepo` — if the second word matches a repo in `JAM_HOME`, the script runs from that repo. Otherwise it's treated as a regular argument.

Platform-aware: `.sh` is preferred on Linux/Mac, `.ps1` on Windows, `.py` everywhere. Built-in commands always take priority.

### Land-then-run shortcut

`jam l<CMD> REPO [ARGS...]` runs `jam land REPO` first, then the `<CMD>` passthrough on the same repo. Typical use: `jam ldeploy myrepo` lands the latest branch and immediately kicks off `deploy.sh`. If there's nothing to land, the script is skipped and jam exits cleanly; if land fails, the failure propagates and the script is not run. Extra args are forwarded to the script. No `--all` — run per repo.

Because `l` is treated as a prefix, scripts whose name starts with `l` are shadowed by this shortcut.

## Attribution & Velocity

If you use Claude Code, jam can restore your personal authorship on AI-assisted commits and optionally track coding velocity.

| | |
|---|---|
| 🔺`jam claim-commits` | Set up commit attribution. Removes "Claude" from AI-assisted commits so they show your name; commits remain traceable. New repos created with `jam new` get attribution automatically after setup. [claim_commits.py](src/jam/commands/claim_commits.py) |
| 🔷`jam reclaim [NAME] [-c N]` | Rewrite commit history on the current branch to reclaim authorship on `@anthropic.com` commits. If a velocity baseline is configured, also tags commits with velocity markers. Use `--commits N` (or `-c N`) to limit how far back reclaim looks instead of processing the entire branch. Requires a clean working tree; force pushes the rewritten branch automatically. Don't use this while Claude Code is working on a diff, as it may create (recoverable, but still) confusion. [reclaim.py](src/jam/commands/reclaim.py) |
| 🟡`jam velocity [NAME]` | Measure coding velocity for a repo. Shows intrinsic (human) and machine-assisted velocity with an acceleration factor. Pick a time period interactively: past week, past month, or all time. [velocity_cmd.py](src/jam/commands/velocity_cmd.py) |
| 🟡`jam tag-velocity enable/disable` | Toggle velocity tagging on commits. When enabled, `jam land` and `jam reclaim` add velocity markers. [tag_velocity.py](src/jam/commands/tag_velocity.py) |
| 🟡`jam autofac-reset` | Clear all attribution and velocity config. Removes `.claude/` from the current repo and resets `claim-commits` state so the workflow can be re-run. [autofac_reset.py](src/jam/commands/autofac_reset.py) |
