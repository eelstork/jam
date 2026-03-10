"""Tests for jam.interactive — cross-platform terminal picker."""

import sys
from unittest.mock import MagicMock, patch


# --- import tests ---


def test_imports_termios_on_unix():
    """On non-Windows, tty and termios should be imported."""
    with patch.object(sys, "platform", "linux"):
        # Force reimport
        import importlib
        import jam.interactive as mod
        importlib.reload(mod)
        assert not mod._WINDOWS


def test_imports_msvcrt_on_windows():
    """On Windows, msvcrt should be imported (mocked since we're on Linux)."""
    mock_msvcrt = MagicMock()
    with patch.object(sys, "platform", "win32"), \
         patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
        import importlib
        import jam.interactive as mod
        importlib.reload(mod)
        assert mod._WINDOWS
    # Restore
    with patch.object(sys, "platform", "linux"):
        import importlib
        importlib.reload(mod)


# --- _read_key tests (Unix path) ---


def test_read_key_enter():
    """Enter key returns 'enter'."""
    import jam.interactive as mod
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = "\r"
        assert mod._read_key(0) == "enter"


def test_read_key_arrow_up():
    """Arrow up escape sequence returns 'up'."""
    import jam.interactive as mod
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.side_effect = ["\x1b", "[A"]
        assert mod._read_key(0) == "up"


def test_read_key_arrow_down():
    """Arrow down escape sequence returns 'down'."""
    import jam.interactive as mod
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.side_effect = ["\x1b", "[B"]
        assert mod._read_key(0) == "down"


def test_read_key_quit():
    """Pressing 'q' returns 'quit'."""
    import jam.interactive as mod
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = "q"
        assert mod._read_key(0) == "quit"


def test_read_key_ctrl_c():
    """Ctrl-C raises KeyboardInterrupt."""
    import jam.interactive as mod
    import pytest
    with patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = "\x03"
        with pytest.raises(KeyboardInterrupt):
            mod._read_key(0)


# --- _read_key tests (Windows path) ---


def test_read_key_windows_arrow_up():
    """Windows arrow up (0xe0 + H) returns 'up'."""
    mock_msvcrt = MagicMock()
    mock_msvcrt.getwch.side_effect = ["\xe0", "H"]
    with patch.object(sys, "platform", "win32"), \
         patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
        import importlib
        import jam.interactive as mod
        importlib.reload(mod)
        assert mod._read_key(None) == "up"
    # Restore
    with patch.object(sys, "platform", "linux"):
        importlib.reload(mod)


def test_read_key_windows_arrow_down():
    """Windows arrow down (0xe0 + P) returns 'down'."""
    mock_msvcrt = MagicMock()
    mock_msvcrt.getwch.side_effect = ["\xe0", "P"]
    with patch.object(sys, "platform", "win32"), \
         patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
        import importlib
        import jam.interactive as mod
        importlib.reload(mod)
        assert mod._read_key(None) == "down"
    # Restore
    with patch.object(sys, "platform", "linux"):
        importlib.reload(mod)


def test_read_key_windows_enter():
    """Windows enter key returns 'enter'."""
    mock_msvcrt = MagicMock()
    mock_msvcrt.getwch.return_value = "\r"
    with patch.object(sys, "platform", "win32"), \
         patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
        import importlib
        import jam.interactive as mod
        importlib.reload(mod)
        assert mod._read_key(None) == "enter"
    # Restore
    with patch.object(sys, "platform", "linux"):
        importlib.reload(mod)


# --- pick tests ---


def test_pick_empty_returns_none():
    """pick([]) should return None immediately."""
    import jam.interactive as mod
    assert mod.pick([]) is None


def test_pick_quit():
    """Pressing quit returns None."""
    import jam.interactive as mod
    with patch("jam.interactive._read_key", return_value="quit"), \
         patch("jam.interactive.termios"), \
         patch("jam.interactive.tty"), \
         patch("sys.stdin") as mock_stdin, \
         patch("sys.stdout"):
        mock_stdin.fileno.return_value = 0
        result = mod.pick(["a", "b", "c"])
        assert result is None


def test_pick_enter_selects_first():
    """Pressing enter immediately selects index 0."""
    import jam.interactive as mod
    with patch("jam.interactive._read_key", return_value="enter"), \
         patch("jam.interactive.termios"), \
         patch("jam.interactive.tty"), \
         patch("sys.stdin") as mock_stdin, \
         patch("sys.stdout"):
        mock_stdin.fileno.return_value = 0
        result = mod.pick(["a", "b", "c"])
        assert result == 0


def test_pick_down_then_enter():
    """Pressing down then enter selects index 1."""
    import jam.interactive as mod
    with patch("jam.interactive._read_key", side_effect=["down", "enter"]), \
         patch("jam.interactive.termios"), \
         patch("jam.interactive.tty"), \
         patch("sys.stdin") as mock_stdin, \
         patch("sys.stdout"):
        mock_stdin.fileno.return_value = 0
        result = mod.pick(["a", "b", "c"])
        assert result == 1
