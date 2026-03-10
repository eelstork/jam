"""Zero-dependency interactive picker for the terminal.

Uses raw ANSI escape codes and tty input. No curses, no external libs.
"""

import sys
import tty
import termios


def _read_key(fd):
    """Read a single keypress, handling arrow key escape sequences."""
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        seq = sys.stdin.read(2)
        if seq == "[A":
            return "up"
        if seq == "[B":
            return "down"
        return "esc"
    if ch in ("\r", "\n"):
        return "enter"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch == "q":
        return "quit"
    return ch


def pick(items, header=None):
    """Show a list of items, let the user arrow through and pick one.

    items: list of (label, description) tuples, or plain strings.
    header: optional line printed above the list.

    Returns the index of the selected item, or None if the user quit.
    """
    if not items:
        return None

    # Normalize to (label, desc) tuples
    normalized = []
    for item in items:
        if isinstance(item, str):
            normalized.append((item, ""))
        else:
            normalized.append((item[0], item[1] if len(item) > 1 else ""))

    cursor = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        # Reserve space so first _render can move up safely
        total_lines = len(normalized) + (1 if header else 0)
        sys.stdout.write("\r\n" * total_lines)
        sys.stdout.flush()
        _render(normalized, cursor, header)

        while True:
            key = _read_key(fd)

            if key == "up":
                cursor = (cursor - 1) % len(normalized)
            elif key == "down":
                cursor = (cursor + 1) % len(normalized)
            elif key == "enter":
                # Clear the menu and return
                _clear(normalized, header)
                return cursor
            elif key in ("quit", "esc"):
                _clear(normalized, header)
                return None

            _render(normalized, cursor, header)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _render(items, cursor, header):
    """Draw the picker. Moves cursor to top-left of our region first."""
    total_lines = len(items) + (1 if header else 0)

    # Move up to overwrite previous render (except on first call)
    sys.stdout.write(f"\x1b[{total_lines}A")
    sys.stdout.write("\r")

    if header:
        sys.stdout.write(f"\x1b[2K{header}\r\n")

    for i, (label, desc) in enumerate(items):
        sys.stdout.write("\x1b[2K")  # clear line
        if i == cursor:
            line = f"  \x1b[7m {label} \x1b[0m"  # inverse video
        else:
            line = f"   {label}"
        if desc:
            line += f"  \x1b[2m{desc}\x1b[0m"
        sys.stdout.write(line + "\r\n")

    sys.stdout.flush()


def _clear(items, header):
    """Erase the picker region."""
    total_lines = len(items) + (1 if header else 0)
    sys.stdout.write(f"\x1b[{total_lines}A")
    for _ in range(total_lines):
        sys.stdout.write("\x1b[2K\r\n")
    sys.stdout.write(f"\x1b[{total_lines}A")
    sys.stdout.flush()
