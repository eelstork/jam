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

**`jam new NAME ["DESCRIPTION"]`** -- spin up a repo on GitHub, clone it locally, push a readme. Add `--public` if you're feeling brave. ([new.py](src/jam/commands/new.py))

**`jam clone SOURCE TARGET ["DESCRIPTION"]`** -- copy a repo as a brand new repo. Fresh git history, new GitHub remote. Great for templates. ([clone.py](src/jam/commands/clone.py))

**`jam list`** -- see what you've got. `--info` pulls the first line from each readme. ([list.py](src/jam/commands/list.py))

**`jam up "MESSAGE"`** -- add everything, commit, push. One shot. `--name REPO` to target a specific repo, `--force` if you need it. ([up.py](src/jam/commands/up.py))

**`jam down [NAME]`** -- pull latest. `--force` throws away local changes first. ([down.py](src/jam/commands/down.py))

**`jam land [NAME]`** -- merge the most recent branch into main. Shows the last 3 commits and asks before doing anything. `--all` lands across all repos at once. `--fast` skips confirmation. ([land.py](src/jam/commands/land.py))

**`jam infuse SOURCE --into TARGET`** -- drop files from one repo into another, auto-commits the result. Bails if anything would overwrite. Also works with a subpath: `jam infuse snippets --into myapp/vendor/ext`. Or just `jam infuse SOURCE` from inside the target repo. ([infuse.py](src/jam/commands/infuse.py))

**`jam undo [NAME]`** -- reverse the last jam command on a repo. Works with `up`, `down`, `land`, and `infuse`. ([undo.py](src/jam/commands/undo.py))

**`jam delete NAME`** -- remove a repo locally. Tags the remote for later cleanup. Re-clone from GitHub to recover. ([delete.py](src/jam/commands/delete.py))

**`jam root`** -- print the current jam root directory. ([root.py](src/jam/commands/root.py))

**`jam set-root PATH`** -- set the jam root directory. Writes to `~/.config/jam/root`. The `JAM_HOME` env var takes priority if set. ([set_root.py](src/jam/commands/set_root.py))

## Command passthrough

Any command that isn't built-in gets routed to a script at the repo root. Drop a `deploy.sh`, `test.py`, or `build.ps1` next to your `.git` and run it with `jam deploy`, `jam test`, `jam build`. Extra arguments are forwarded: `jam build --release v2` runs `bash build.sh --release v2`.

Target a specific repo with `jam deploy myrepo` — if the second word matches a repo in `JAM_HOME`, the script runs from that repo. Otherwise it's treated as a regular argument.

Platform-aware: `.sh` is preferred on Linux/Mac, `.ps1` on Windows, `.py` everywhere. Built-in commands always take priority.
