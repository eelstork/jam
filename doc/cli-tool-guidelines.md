# CLI Tool Guidelines

How jam is built, and the principles behind the decisions.

## One file per command

Every command lives in its own file under `src/jam/commands/`. The file is the command — no registries, no class hierarchies, no routing tables. You add a command by writing a file and wiring it into `cli.py`. You remove one by deleting the file.

This keeps commands independent, easy to read in isolation, and easy to link from documentation.

## install.py / uninstall.py

Top-level scripts that do the obvious thing. `python install.py` installs jam. `python uninstall.py` removes it. No flags, no options, no surprises.

Both wrap pip under the hood, so experienced Python users can use `pip install -e .` and `pip uninstall jam` directly. The scripts exist for people who don't want to think about pip.

## Documentation links to source

Every command entry in the README links directly to its source file. If you want to know what `jam land` does, you click through and read the code. This builds trust — nothing is hidden — and it keeps documentation honest, because a link to a messy file is a reminder to clean it up.

## Interactive front-end

Running `jam` with no arguments opens an interactive picker. Arrow keys to browse, enter to select. Zero external dependencies — just ANSI escape codes and tty input.

This matters for three audiences:

- **New users** who don't yet know the commands. The picker shows everything available and lets them explore without reading docs first.
- **Casual users** who use jam once a week and will never memorise the command names. The picker is faster than `jam --help` and more forgiving than typos.
- **Accessibility** — not everyone is comfortable composing commands from memory. A visual menu with keyboard navigation lowers the barrier.

The interactive mode is a front-end, not a crutch. Every action it offers maps 1:1 to a CLI command, so power users lose nothing.

## Shared helpers, not frameworks

Common operations (resolving repos, running shell commands, managing undo breadcrumbs) live in `helpers.py`. Commands import what they need. There is no base class, no plugin system, no lifecycle hooks. If a helper doesn't exist yet, write a function.

## Configuration

Configuration is minimal and file-based. `jam set-root` writes the root path to `~/.config/jam/root` — a plain text file. The `JAM_HOME` environment variable overrides it when set. No YAML, no TOML, no dotfiles with dozens of keys.

---

## Provisional

Aspects that feel right but haven't been stress-tested yet. Subject to revision.

**Click for argument parsing.** Click handles args, options, flags, and help text with minimal boilerplate. It's the one external dependency in the command layer. If it ever becomes a burden, the per-file structure means commands can be migrated individually.

**Undo via breadcrumbs.** Each command drops a small JSON file in `.git/` recording what it did. `jam undo` reads it and reverses the action. This is simple and local but limited to one level of undo. Whether that's enough remains to be seen.

**No shell profile modification.** `jam set-root` writes a config file rather than appending `export JAM_HOME=...` to `.bashrc` or `.zshrc`. Touching shell profiles is fragile and presumptuous. The trade-off is that the env var approach requires the user to set it up themselves — but `set-root` exists precisely so most users never need to.

**Flat repo structure.** All repos sit directly under `JAM_HOME`, no nesting. This keeps `jam list` and repo resolution simple. It may not scale for users with hundreds of repos, but it hasn't been a problem yet.
