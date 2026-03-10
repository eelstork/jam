# jam

Git without the ceremony. Create repos, push code, land branches -- all in a few keystrokes.

Jam keeps all your repos under one roof (`JAM_HOME`) and talks to GitHub via `gh`. No config files, no boilerplate. Just the stuff you actually do, made fast.

## Setup

Requires Python 3.10+, [git](https://git-scm.com), and [gh](https://cli.github.com) (authenticated).

```
pip install -e .
```

Set `JAM_HOME` to where you keep your repos:

```
export JAM_HOME=~/dev
```

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
