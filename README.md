# jam

Git without the ceremony. Create repos, push code, land branches -- all in a few keystrokes.

Jam keeps all your repos under one roof (`JAM_HOME`) and talks to GitHub via `gh`. No config files, no boilerplate. Just the stuff you actually do, made fast.

Requires Python 3.10+, [git](https://git-scm.com), and [gh](https://cli.github.com) (authenticated).

Install via `python install.py`, or `pip install -e .` if you prefer the standard Python way. To remove: `python uninstall.py`.

## Setup

Point jam at your repos directory:

```
jam set-root ~/dev
```

Or set the `JAM_HOME` environment variable if you prefer.

## Commands

**`jam new NAME ["DESCRIPTION"]`** -- spin up a repo on GitHub, clone it locally, push a readme. `--public` to make it public. Alias: `jam create`.
[new.py](src/jam/commands/new.py)

**`jam clone SOURCE TARGET ["DESCRIPTION"]`** -- copy a repo as a brand new repo. Fresh git history, new GitHub remote. Great for templates. `--public` to make it public.
[clone.py](src/jam/commands/clone.py)

**`jam list`** -- see what you've got. `--info` pulls the first line from each readme.
[list.py](src/jam/commands/list.py)

**`jam up "MESSAGE"`** -- add everything, commit, push. One shot. `--name REPO` to target a specific repo, `--force` if you need it.
[up.py](src/jam/commands/up.py)

**`jam down [NAME]`** -- pull latest. `--force` throws away local changes first.
[down.py](src/jam/commands/down.py)

**`jam land [NAME]`** -- merge the most recent branch into main and show all landed commits. `--all` lands across all repos at once.
[land.py](src/jam/commands/land.py)

**`jam infuse SOURCE --into TARGET`** -- drop files from one repo into another, auto-commits the result. Bails if anything would overwrite. Also works with a subpath: `jam infuse snippets --into myapp/vendor/ext`. Or just `jam infuse SOURCE` from inside the target repo.
[infuse.py](src/jam/commands/infuse.py)

**`jam undo [NAME]`** -- reverse the last jam command on a repo. Works with `up`, `down`, `land`, and `infuse`.
[undo.py](src/jam/commands/undo.py)

**`jam delete NAME`** -- remove a repo locally. Tags the remote for later cleanup. Re-clone from GitHub to recover.
[delete.py](src/jam/commands/delete.py)

**`jam root`** -- print the current jam root directory.
[root.py](src/jam/commands/root.py)

**`jam set-root PATH`** -- set the jam root directory. Writes to `~/.config/jam/root`. The `JAM_HOME` env var takes priority if set.
[set_root.py](src/jam/commands/set_root.py)

**`jam update`** -- pull the latest jam source and reinstall. Runs `git pull` + `pip install -e .` from wherever jam is installed.
[update.py](src/jam/commands/update.py)

## Command passthrough

Any command that isn't built-in gets routed to a script at the repo root. Drop a `deploy.sh`, `test.py`, or `build.ps1` next to your `.git` and run it with `jam deploy`, `jam test`, `jam build`. Extra arguments are forwarded: `jam build --release v2` runs `bash build.sh --release v2`.

Target a specific repo with `jam deploy myrepo` — if the second word matches a repo in `JAM_HOME`, the script runs from that repo. Otherwise it's treated as a regular argument.

Platform-aware: `.sh` is preferred on Linux/Mac, `.ps1` on Windows, `.py` everywhere. Built-in commands always take priority.

## Attribution & Velocity

If you use Claude Code, jam can restore your personal authorship on AI-assisted commits and optionally track coding velocity.

**`jam claim-commits`** -- set up commit attribution. Removes "Claude" from AI-assisted commits so they show your name; commits remain traceable. New repos created with `jam new` or `jam clone` get attribution automatically after setup.
[claim_commits.py](src/jam/commands/claim_commits.py)

**`jam reclaim [NAME]`** -- rewrite commit history to reclaim authorship on `@anthropic.com` commits. If a velocity baseline is configured, also tags commits with velocity markers. All SHAs will change.
[reclaim.py](src/jam/commands/reclaim.py)

**`jam velocity [NAME]`** -- measure coding velocity for a repo. Shows intrinsic (human) and machine-assisted velocity with an acceleration factor. Pick a time period interactively: past week, past month, or all time.
[velocity_cmd.py](src/jam/commands/velocity_cmd.py)

**`jam autofac-reset`** -- clear all attribution and velocity config. Removes `.claude/` from the current repo and resets `claim-commits` state so the workflow can be re-run.
[autofac_reset.py](src/jam/commands/autofac_reset.py)
