"""Unit tests for agentfront.taui.render.ansi — render_ansi."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from agentfront.taui.render.ansi import _FRAME_GLYPHS, render_ansi
from agentfront.taui.state import (
    Background,
    ConversationLine,
    Header,
    Panel,
    PanelItem,
    Status,
    TAUIState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_state(
    title: str = "MyApp",
    version: str = "0.1.0",
    subtitle: str = "Test",
    focused: str = "panel.search.search.query",
    severity: str = "info",
    message: str = "Ready",
) -> TAUIState:
    """Return a populated TAUIState for testing render_ansi."""
    return TAUIState(
        header=Header(title=title, version=version, subtitle=subtitle),
        focused=focused,
        panels=[
            Panel(
                id="panel.search",
                title="Search",
                visible=True,
                items=[
                    PanelItem(
                        id="panel.search.search.query",
                        label="Query",
                        status="available",
                    ),
                    PanelItem(
                        id="panel.search.search.advanced",
                        label="Advanced",
                        status="disabled",
                    ),
                ],
            ),
            Panel(
                id="panel.feedback",
                title="Feedback",
                visible=False,
                items=[
                    PanelItem(
                        id="panel.feedback.record",
                        label="Record",
                        status="available",
                    ),
                ],
            ),
            Panel(
                id="panel.settings",
                title="Settings",
                visible=True,
                items=[
                    PanelItem(
                        id="panel.settings.theme",
                        label="Theme",
                        status="available",
                    ),
                ],
            ),
        ],
        status=Status(severity=severity, message=message),
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_ansi_is_deterministic() -> None:
    """render_ansi(s) == render_ansi(s) — byte-identical output."""
    state = _build_state()
    assert render_ansi(state) == render_ansi(state)


def test_render_ansi_no_clock_or_random() -> None:
    """The module must not import time, datetime, random, or uuid."""
    source = (
        Path(__file__).resolve().parent.parent.parent / "agentfront" / "taui" / "render" / "ansi.py"
    )
    tree = ast.parse(source.read_text())
    forbidden = {"time", "datetime", "random", "uuid"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden, f"Forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert (
                    node.module.split(".")[0] not in forbidden
                ), f"Forbidden import: {node.module}"


def test_render_ansi_no_third_party_imports() -> None:
    """The module imports only stdlib + agentfront.taui."""
    source = (
        Path(__file__).resolve().parent.parent.parent / "agentfront" / "taui" / "render" / "ansi.py"
    )
    tree = ast.parse(source.read_text())
    stdlib_modules = (
        set(sys.stdlib_module_names)
        if hasattr(sys, "stdlib_module_names")
        else {
            "__future__",
            "ast",
            "dataclasses",
            "importlib",
            "json",
            "os",
            "pathlib",
            "re",
            "sys",
            "typing",
        }
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_modules or top.startswith(
                    "agentfront"
                ), f"Third-party import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                assert top in stdlib_modules or top.startswith(
                    "agentfront"
                ), f"Third-party import: {node.module}"


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------


def test_frame_shows_header() -> None:
    """The header line contains title, version, and subtitle."""
    state = _build_state()
    output = render_ansi(state)
    assert "MyApp" in output
    assert "0.1.0" in output
    assert "Test" in output


def test_frame_shows_panel_items() -> None:
    """Visible panel items appear in the output."""
    state = _build_state()
    output = render_ansi(state)
    assert "Query" in output
    assert "Advanced" in output
    assert "Theme" in output


def test_frame_shows_focused_marker() -> None:
    """The focused item has a leading '> ' marker."""
    state = _build_state()
    output = render_ansi(state)
    assert "> Query" in output


def test_frame_shows_status_line() -> None:
    """The status line appears at the end, prefixed with a frame glyph."""
    state = _build_state()
    output = render_ansi(state)
    assert "◐ [info] Ready" in output


def test_hidden_panel_not_rendered() -> None:
    """A hidden panel's title does NOT appear in the output."""
    state = _build_state()
    output = render_ansi(state)
    assert "Feedback" not in output


def test_severity_and_message_in_status() -> None:
    """Status severity and message are rendered with a leading frame glyph."""
    state = _build_state(severity="warning", message="Disk space low")
    output = render_ansi(state)
    assert "◐ [warning] Disk space low" in output


def test_focused_on_input_prompt() -> None:
    """When focused is 'input.prompt', render is still deterministic."""
    state = _build_state(focused="input.prompt")
    output = render_ansi(state)
    # No item matches, so no "> " prefix on any item
    assert "> " not in output
    # Still deterministic
    assert render_ansi(state) == render_ansi(state)


def test_focused_on_panel_id() -> None:
    """When focused is a panel id, render is still deterministic."""
    state = _build_state(focused="panel.search")
    output = render_ansi(state)
    # No item matches the panel id, so no "> " prefix
    assert "> " not in output
    assert render_ansi(state) == render_ansi(state)


def test_empty_state() -> None:
    """A default (empty) state renders without error."""
    state = TAUIState()
    output = render_ansi(state)
    assert isinstance(output, str)
    assert render_ansi(state) == render_ansi(state)


# ---------------------------------------------------------------------------
# Frame glyph
# ---------------------------------------------------------------------------


def test_frame_glyph_constant() -> None:
    """_FRAME_GLYPHS contains exactly the four half-circle spinner glyphs."""
    assert _FRAME_GLYPHS == ("◐", "◓", "◑", "◒")


def test_frame_glyph_frame_zero() -> None:
    """frame=0 → ◐ on the status line."""
    state = TAUIState(background=Background(frame=0))
    output = render_ansi(state)
    assert output.split("\n")[-1].startswith("◐")


def test_frame_glyph_frame_one() -> None:
    """frame=1 → ◓ on the status line."""
    state = TAUIState(background=Background(frame=1))
    output = render_ansi(state)
    assert output.split("\n")[-1].startswith("◓")


def test_frame_glyph_frame_two() -> None:
    """frame=2 → ◑ on the status line."""
    state = TAUIState(background=Background(frame=2))
    output = render_ansi(state)
    assert output.split("\n")[-1].startswith("◑")


def test_frame_glyph_frame_three() -> None:
    """frame=3 → ◒ on the status line."""
    state = TAUIState(background=Background(frame=3))
    output = render_ansi(state)
    assert output.split("\n")[-1].startswith("◒")


def test_frame_glyph_wraps_at_four() -> None:
    """frame=4 wraps back to ◐ (same as frame=0)."""
    state = TAUIState(background=Background(frame=4))
    output = render_ansi(state)
    assert output.split("\n")[-1].startswith("◐")


# ---------------------------------------------------------------------------
# Conversation section
# ---------------------------------------------------------------------------


def test_conversation_section_renders() -> None:
    """Non-empty conversation renders a ## Conversation section."""
    state = TAUIState(
        conversation=[
            ConversationLine(text="Hello"),
            ConversationLine(text="World"),
        ]
    )
    output = render_ansi(state)
    assert "## Conversation" in output
    assert "  Hello" in output
    assert "  World" in output


def test_conversation_two_space_indent() -> None:
    """Each conversation line is indented with exactly two spaces."""
    state = TAUIState(conversation=[ConversationLine(text="Step 1")])
    output = render_ansi(state)
    lines = output.split("\n")
    indented = [ln for ln in lines if ln.startswith("  Step")]
    assert indented, "Expected an indented conversation line"
    assert indented[0] == "  Step 1"


def test_conversation_collapse_renders() -> None:
    """Consecutive-duplicate collapse renders 'text ×N' in the section."""
    state = TAUIState(conversation=[ConversationLine(text="Retry", count=3)])
    output = render_ansi(state)
    assert "  Retry ×3" in output


def test_empty_conversation_no_section() -> None:
    """Empty conversation list renders no ## Conversation section."""
    state = _build_state()
    output = render_ansi(state)
    assert "## Conversation" not in output


def test_conversation_appears_before_status_line() -> None:
    """## Conversation section appears before the status line in the output."""
    state = TAUIState(conversation=[ConversationLine(text="Step 1")])
    output = render_ansi(state)
    lines = output.split("\n")
    conv_idx = next(i for i, ln in enumerate(lines) if ln == "## Conversation")
    status_idx = next(i for i, ln in enumerate(lines) if ln and ln[0] in "◐◓◑◒")
    assert conv_idx < status_idx


def test_render_ansi_deterministic_with_conversation() -> None:
    """Same state with a conversation always produces identical output."""
    state = TAUIState(
        conversation=[
            ConversationLine(text="A"),
            ConversationLine(text="B", count=2),
        ]
    )
    assert render_ansi(state) == render_ansi(state)
