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

**`jam new NAME ["DESCRIPTION"]`** -- spin up a repo on GitHub, clone it locally, push a readme. Add `--public` if you're feeling brave.

**`jam clone SOURCE TARGET ["DESCRIPTION"]`** -- copy a repo as a brand new repo. Fresh git history, new GitHub remote. Great for templates.

**`jam list`** -- see what you've got. `--info` pulls the first line from each readme.

**`jam up [NAME] "MESSAGE"`** -- add everything, commit, push. One shot. `--force` if you need it.

**`jam down [NAME]`** -- pull latest. `--force` throws away local changes first.

**`jam land [NAME]`** -- merge the most recent branch into main, clean up after. Shows the last 3 commits and asks before doing anything. `--all` shows every commit, `--fast` just lands it silently.

**`jam infuse NAME into TARGET`** -- drop files from one repo into another. Bails if anything would overwrite. Also works with a subpath: `jam infuse snippets into myapp/vendor/ext`. Or just `jam infuse NAME` from inside the target repo.

**`jam delete NAME`** -- remove a repo locally and on GitHub. Asks twice because it should.
