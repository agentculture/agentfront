"""Unit tests for agentfront.taui.widgets.slash_autocomplete."""

from __future__ import annotations

import types

from agentfront.taui.widgets.slash_autocomplete import (
    TAG_ICON,
    TAG_TEXT,
    format_tags,
    render_slash_autocomplete,
)


def _match(
    name: str = "cmd",
    arg_hint: str = "",
    description: str = "A command",
    group: str = "controls",
    tags: list[str] | None = None,
) -> object:
    """Build a duck-typed match spec using SimpleNamespace."""
    return types.SimpleNamespace(
        name=name,
        arg_hint=arg_hint,
        description=description,
        group=group,
        tags=tags if tags is not None else [],
    )


# ---------------------------------------------------------------------------
# format_tags
# ---------------------------------------------------------------------------


def test_format_tags_text_known() -> None:
    """Known tag renders as bracketed text badge."""
    assert format_tags(["read-only"]) == "[read-only]"


def test_format_tags_icons_known() -> None:
    """Known tag in icons mode renders the emoji badge."""
    result = format_tags(["read-only"], "icons")
    assert TAG_ICON["read-only"] in result


def test_format_tags_text_unknown_falls_back() -> None:
    """Unknown tag falls back to [tag] in text mode."""
    assert format_tags(["wat"]) == "[wat]"


def test_format_tags_icons_unknown_falls_back_to_bare_word() -> None:
    """Unknown tag falls back to the bare word in icons mode."""
    assert format_tags(["wat"], "icons") == "wat"


def test_format_tags_empty_returns_empty_string() -> None:
    """Empty tag list returns an empty string."""
    assert format_tags([]) == ""


def test_format_tags_multiple_joined_by_space() -> None:
    """Multiple tags are space-joined."""
    result = format_tags(["read-only", "git"])
    assert "[read-only]" in result
    assert "[git]" in result
    # The two badges are separated by a space.
    assert result == "[read-only] [git]"


def test_format_tags_custom_tag_text_overrides_default() -> None:
    """Custom tag_text dict overrides the module-level default."""
    assert format_tags(["foo"], tag_text={"foo": "<FOO>"}) == "<FOO>"


def test_format_tags_custom_tag_icon_overrides_default() -> None:
    """Custom tag_icon dict overrides the module-level default in icons mode."""
    assert format_tags(["bar"], "icons", tag_icon={"bar": "🎯"}) == "🎯"


def test_format_tags_never_raises_on_unknown() -> None:
    """format_tags does not raise for any tag value, including odd strings."""
    result = format_tags(["unknown-tag-xyz"])
    assert "[unknown-tag-xyz]" in result


# ---------------------------------------------------------------------------
# render_slash_autocomplete — vanish case
# ---------------------------------------------------------------------------


def test_render_empty_matches_returns_empty_string() -> None:
    """Empty matches list renders as empty string (vanish case)."""
    assert render_slash_autocomplete([]) == ""


# ---------------------------------------------------------------------------
# render_slash_autocomplete — heading lines
# ---------------------------------------------------------------------------


def test_render_group_heading_contains_folder_icon() -> None:
    """Group heading line contains the 📁 icon."""
    m = _match(name="status", group="controls")
    result = render_slash_autocomplete([m])
    assert "📁" in result


def test_render_group_heading_contains_group_title() -> None:
    """Group heading line contains the human-readable group title."""
    m = _match(name="status", group="controls")
    result = render_slash_autocomplete([m])
    assert "Controls" in result


# ---------------------------------------------------------------------------
# render_slash_autocomplete — command lines
# ---------------------------------------------------------------------------


def test_render_command_line_contains_slash_name() -> None:
    """Command line contains /name."""
    m = _match(name="help", group="controls")
    result = render_slash_autocomplete([m])
    assert "/help" in result


def test_render_selected_index_has_chevron_marker() -> None:
    """The selected row is marked with the › chevron."""
    m = _match(name="go", group="controls")
    result = render_slash_autocomplete([m], selected=0)
    assert "›" in result


def test_render_selected_index_has_reverse_video_sgr() -> None:
    """The selected row uses reverse-video SGR (ESC[7m)."""
    m = _match(name="go", group="controls")
    result = render_slash_autocomplete([m], selected=0)
    assert "\x1b[7m" in result


def test_render_unselected_row_has_no_chevron() -> None:
    """An unselected row does not carry the › marker."""
    matches = [
        _match(name="a", group="controls"),
        _match(name="b", group="controls"),
    ]
    result = render_slash_autocomplete(matches, selected=0)
    # Find all lines that mention 'b' — none should have ›.
    b_lines = [ln for ln in result.splitlines() if "/b" in ln]
    assert b_lines, "Expected a line for /b"
    assert all("›" not in ln for ln in b_lines)


def test_render_selected_dim_summary_sub_line() -> None:
    """Selected row with a non-empty description adds a dim sub-line below it."""
    m = _match(name="run", description="Execute something", group="controls")
    result = render_slash_autocomplete([m], selected=0)
    assert "\x1b[2m" in result
    assert "Execute something" in result


def test_render_multiple_groups_show_separate_headings() -> None:
    """Matches from different groups render under separate group headings."""
    m1 = _match(name="a", group="controls")
    m2 = _match(name="b", group="inspect")
    result = render_slash_autocomplete([m1, m2])
    assert "Controls" in result
    assert "Inspect" in result


def test_render_arg_hint_included() -> None:
    """A non-empty arg_hint appears on the command line."""
    m = _match(name="load", arg_hint="<file>", group="controls")
    result = render_slash_autocomplete([m])
    assert "<file>" in result


def test_render_tags_included_in_command_line() -> None:
    """Tags are rendered on the command line."""
    m = _match(name="read", tags=["read-only"], group="controls")
    result = render_slash_autocomplete([m])
    assert TAG_TEXT["read-only"] in result


# ---------------------------------------------------------------------------
# Genericity: custom groups
# ---------------------------------------------------------------------------


def test_render_custom_groups_controls_heading() -> None:
    """Passing custom groups makes the custom heading label appear."""
    m = _match(name="foo", group="x")
    result = render_slash_autocomplete([m], groups=[("x", "Custom")])
    assert "Custom" in result
    assert "📁" in result


def test_render_custom_groups_command_appears_under_heading() -> None:
    """The command name appears in the output when its group is in custom groups."""
    m = _match(name="foo", group="x")
    result = render_slash_autocomplete([m], groups=[("x", "Custom")])
    assert "/foo" in result


def test_render_unknown_group_still_shown_at_end() -> None:
    """A match whose group is not listed in groups is appended and still rendered."""
    m = _match(name="bar", group="hidden")
    result = render_slash_autocomplete([m], groups=[("controls", "Controls")])
    assert "/bar" in result


def test_render_custom_tag_text_overrides_in_output() -> None:
    """Custom tag_text passed to render_slash_autocomplete appears in output."""
    m = _match(name="cmd", tags=["foo"], group="controls")
    result = render_slash_autocomplete([m], tag_text={"foo": "<FOO>"})
    assert "<FOO>" in result


def test_render_custom_tag_icon_overrides_in_output() -> None:
    """Custom tag_icon passed with style='icons' appears in output."""
    m = _match(name="cmd", tags=["bar"], group="controls")
    result = render_slash_autocomplete([m], style="icons", tag_icon={"bar": "🎯"})
    assert "🎯" in result
