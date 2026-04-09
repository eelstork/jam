"""Tests for jam remix — parse, summarize, deduplicate, and share CLAUDE.md directives."""

import json
import os
from unittest.mock import patch

from click.testing import CliRunner

from jam.cli import main
from jam.commands.remix import (
    _find_claude_md_files,
    _parse_directives,
    _write_directive_to_claude_md,
    _deduplicate,
    _summarize_directives,
)


# --- _find_claude_md_files ---


def test_find_claude_md_files(tmp_path):
    """Should find CLAUDE.md files in repos under jam_home."""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "CLAUDE.md").write_text("# CLAUDE.md\n- Do thing\n")
    (tmp_path / "beta").mkdir()
    # beta has no CLAUDE.md
    (tmp_path / "gamma").mkdir()
    (tmp_path / "gamma" / "CLAUDE.md").write_text("# CLAUDE.md\n- Other\n")
    # plain file, not a directory
    (tmp_path / "notadir.txt").write_text("hi")

    result = _find_claude_md_files(str(tmp_path))
    names = [name for name, _ in result]
    assert names == ["alpha", "gamma"]


def test_find_claude_md_files_empty(tmp_path):
    """Should return empty list when no repos have CLAUDE.md."""
    (tmp_path / "repo").mkdir()
    result = _find_claude_md_files(str(tmp_path))
    assert result == []


# --- _parse_directives ---


def test_parse_directives_bullets():
    """Should parse bullet items as directives."""
    text = "# CLAUDE.md\n\n## Testing\n\n- Run pytest before committing\n- Check coverage\n"
    result = _parse_directives(text, "myrepo")
    assert len(result) == 2
    assert result[0]["text"] == "Run pytest before committing"
    assert result[0]["repo"] == "myrepo"
    assert result[0]["section"] == "Testing"
    assert result[1]["text"] == "Check coverage"
    assert result[1]["section"] == "Testing"


def test_parse_directives_multiple_sections():
    """Should track which section each directive belongs to."""
    text = (
        "# CLAUDE.md\n\n"
        "## Style\n\n- Use snake_case\n\n"
        "## Testing\n\n- Run tests\n"
    )
    result = _parse_directives(text, "repo")
    assert len(result) == 2
    assert result[0]["section"] == "Style"
    assert result[1]["section"] == "Testing"


def test_parse_directives_no_section():
    """Directives outside sections should have empty section."""
    text = "# CLAUDE.md\n\nAlways be concise\n"
    result = _parse_directives(text, "repo")
    assert len(result) == 1
    assert result[0]["text"] == "Always be concise"
    assert result[0]["section"] == ""


def test_parse_directives_plain_text_lines():
    """Non-bullet, non-heading lines are also treated as directives."""
    text = "# CLAUDE.md\n\nUse TypeScript for all new code\n"
    result = _parse_directives(text, "repo")
    assert len(result) == 1
    assert result[0]["text"] == "Use TypeScript for all new code"


def test_parse_directives_skips_headings():
    """H1 and H2 headings should not appear as directives."""
    text = "# Title\n\n## Section\n\n- Actual directive\n"
    result = _parse_directives(text, "repo")
    assert len(result) == 1
    assert result[0]["text"] == "Actual directive"


def test_parse_directives_empty():
    """Empty file should yield no directives."""
    result = _parse_directives("", "repo")
    assert result == []


def test_parse_directives_headings_only():
    """File with only headings should yield no directives."""
    result = _parse_directives("# Title\n\n## Section\n", "repo")
    assert result == []


# --- _write_directive_to_claude_md ---


def test_write_directive_creates_file(tmp_path):
    """Should create CLAUDE.md if it doesn't exist."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    directive = {"text": "Run tests", "repo": "other", "section": "Testing"}

    result = _write_directive_to_claude_md(str(repo), directive)
    assert result is True

    content = (repo / "CLAUDE.md").read_text()
    assert "## Testing" in content
    assert "- Run tests" in content


def test_write_directive_appends_to_existing_section(tmp_path):
    """Should append under an existing section."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Testing\n\n- Existing rule\n")
    directive = {"text": "Check coverage", "repo": "other", "section": "Testing"}

    result = _write_directive_to_claude_md(str(repo), directive)
    assert result is True

    content = (repo / "CLAUDE.md").read_text()
    assert "- Existing rule" in content
    assert "- Check coverage" in content


def test_write_directive_adds_new_section(tmp_path):
    """Should create a new section if it doesn't exist."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Style\n\n- Be concise\n")
    directive = {"text": "Run tests", "repo": "other", "section": "Testing"}

    result = _write_directive_to_claude_md(str(repo), directive)
    assert result is True

    content = (repo / "CLAUDE.md").read_text()
    assert "## Style" in content
    assert "## Testing" in content
    assert "- Run tests" in content


def test_write_directive_skips_duplicate(tmp_path):
    """Should not add a directive that already exists in the file."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Testing\n\n- Run tests\n")
    directive = {"text": "Run tests", "repo": "other", "section": "Testing"}

    result = _write_directive_to_claude_md(str(repo), directive)
    assert result is False

    content = (repo / "CLAUDE.md").read_text()
    assert content.count("Run tests") == 1


def test_write_directive_no_section(tmp_path):
    """Should append at end when directive has no section."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n")
    directive = {"text": "Be concise", "repo": "other", "section": ""}

    result = _write_directive_to_claude_md(str(repo), directive)
    assert result is True

    content = (repo / "CLAUDE.md").read_text()
    assert "- Be concise" in content


# --- _summarize_directives ---


def test_summarize_fallback_when_keryx_unavailable():
    """Should truncate directives as fallback when keryx fails."""
    directives = [
        {"text": "Always run the full test suite before committing changes", "repo": "r", "section": ""},
        {"text": "Short rule", "repo": "r", "section": ""},
    ]
    with patch("jam.commands.remix._ask_keryx", return_value=None):
        result = _summarize_directives(directives)
    assert len(result) == 2
    assert result[0] == directives[0]["text"][:50]
    assert result[1] == "Short rule"


def test_summarize_uses_keryx_response():
    """Should parse keryx JSON response for summaries."""
    directives = [
        {"text": "Run tests", "repo": "r", "section": ""},
        {"text": "Check coverage", "repo": "r", "section": ""},
    ]
    with patch("jam.commands.remix._ask_keryx", return_value='["run test suite", "verify coverage"]'):
        result = _summarize_directives(directives)
    assert result == ["run test suite", "verify coverage"]


def test_summarize_fallback_on_bad_json():
    """Should fall back to truncation if keryx returns bad JSON."""
    directives = [{"text": "Do thing", "repo": "r", "section": ""}]
    with patch("jam.commands.remix._ask_keryx", return_value="not json"):
        result = _summarize_directives(directives)
    assert result == ["Do thing"]


def test_summarize_fallback_on_length_mismatch():
    """Should fall back if keryx returns wrong number of summaries."""
    directives = [
        {"text": "Rule one", "repo": "r", "section": ""},
        {"text": "Rule two", "repo": "r", "section": ""},
    ]
    with patch("jam.commands.remix._ask_keryx", return_value='["only one"]'):
        result = _summarize_directives(directives)
    assert len(result) == 2
    assert result[0] == "Rule one"


# --- _deduplicate ---


def test_deduplicate_single_item():
    """Single directive should pass through unchanged."""
    directives = [{"text": "Only one", "repo": "r", "section": ""}]
    summaries = ["only one"]
    result_d, result_s = _deduplicate(directives, summaries)
    assert result_d == directives
    assert result_s == summaries


def test_deduplicate_uses_keryx():
    """Should keep items at indices returned by keryx."""
    directives = [
        {"text": "Run tests", "repo": "a", "section": ""},
        {"text": "Execute test suite", "repo": "b", "section": ""},
        {"text": "Check lint", "repo": "a", "section": ""},
    ]
    summaries = ["run tests", "execute tests", "check lint"]
    # keryx says keep 1 and 3 (drop 2 as duplicate of 1)
    with patch("jam.commands.remix._ask_keryx", return_value="[1, 3]"):
        result_d, result_s = _deduplicate(directives, summaries)
    assert len(result_d) == 2
    assert result_d[0]["text"] == "Run tests"
    assert result_d[1]["text"] == "Check lint"
    assert result_s == ["run tests", "check lint"]


def test_deduplicate_fallback_on_failure():
    """Should return everything if keryx fails."""
    directives = [
        {"text": "Rule one", "repo": "a", "section": ""},
        {"text": "Rule two", "repo": "b", "section": ""},
    ]
    summaries = ["one", "two"]
    with patch("jam.commands.remix._ask_keryx", return_value=None):
        result_d, result_s = _deduplicate(directives, summaries)
    assert result_d == directives
    assert result_s == summaries


# --- remix CLI command ---


def test_remix_no_claude_md(tmp_path):
    """remix should fail when no CLAUDE.md files exist."""
    (tmp_path / "myrepo").mkdir()
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["remix"])
    assert result.exit_code != 0
    assert "No CLAUDE.md files found" in result.output


def test_remix_non_interactive_lists_directives(tmp_path):
    """In non-interactive mode, remix should list directives."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Testing\n\n- Run tests\n- Check lint\n")

    with patch("jam.commands.remix._ask_keryx", return_value=None):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        # CliRunner is non-interactive by default (stdin is not a tty)
        result = runner.invoke(main, ["remix"])
    assert result.exit_code == 0
    assert "Found CLAUDE.md in 1 repo(s)" in result.output
    assert "2 unique directive(s) found" in result.output
    assert "[myrepo]" in result.output


def test_remix_unsupported_target(tmp_path):
    """remix should reject targets other than claude.md."""
    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["remix", "something-else"])
    assert result.exit_code != 0
    assert "Only 'claude.md' is supported" in result.output


def test_remix_no_directives(tmp_path):
    """remix should fail when CLAUDE.md exists but has no directives."""
    repo = tmp_path / "myrepo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Empty Section\n")

    runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
    result = runner.invoke(main, ["remix"])
    assert result.exit_code != 0
    assert "No directives found" in result.output


def test_remix_multiple_repos(tmp_path):
    """remix should aggregate directives across repos."""
    alpha = tmp_path / "alpha"
    alpha.mkdir()
    (alpha / "CLAUDE.md").write_text("# CLAUDE.md\n\n- Use TypeScript\n")

    beta = tmp_path / "beta"
    beta.mkdir()
    (beta / "CLAUDE.md").write_text("# CLAUDE.md\n\n- Run pytest\n")

    with patch("jam.commands.remix._ask_keryx", return_value=None):
        runner = CliRunner(env={"JAM_HOME": str(tmp_path)})
        result = runner.invoke(main, ["remix"])
    assert result.exit_code == 0
    assert "Found CLAUDE.md in 2 repo(s)" in result.output
    assert "[alpha]" in result.output
    assert "[beta]" in result.output
