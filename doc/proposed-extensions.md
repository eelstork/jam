# Proposed Extensions

## Missing from the core

Commands that feel like they should exist alongside the current set.

**`jam status [NAME]`** -- quick overview of a repo: current branch, dirty files, ahead/behind remote. Basically `git status` but less noisy and works by name from anywhere.

**`jam log [NAME]`** -- recent commits, compact. Maybe last 10 by default, `--all` for the full history. Saves you from `cd`-ing around.

**`jam branch NAME [REPO]`** -- create a branch and switch to it. The counterpart to `land`. Keeps things symmetrical: branch, work, up, land.

**`jam rename OLD NEW`** -- rename a repo locally and on GitHub. Annoying to do by hand, easy to script.

**`jam archive NAME`** -- archive a repo on GitHub and maybe move the local folder into a `.archive/` subfolder. Softer than delete.

## Fun or useful additions

Things that aren't strictly necessary but would be nice to have.

**`jam grab USER/REPO [NAME]`** -- clone someone else's repo into JAM_HOME. Optionally rename it locally. For when you want to poke at someone's code without the usual `cd ~/wherever && git clone` dance.

**`jam diff [NAME]`** -- show what changed since last commit. Basically `git diff` but accessible by name and from anywhere.

**`jam todo [NAME]`** -- scan for TODO/FIXME/HACK comments across the repo and list them. Quick way to see what's hanging.

**`jam mirror SOURCE TARGET`** -- like clone but keeps a link to the original. Pull upstream changes later. Useful for maintaining a fork without the GitHub fork UI.

**`jam stats [NAME]`** -- lines of code, number of commits, top contributors, last activity. Dashboard vibes.

**`jam open [NAME]`** -- open the GitHub repo page in your browser. Small but saves a trip to the browser.

**`jam init`** -- interactive first-time setup. Sets `JAM_HOME`, checks that `gh` is authed, maybe adds the env var to your shell profile. Smooth onboarding.
