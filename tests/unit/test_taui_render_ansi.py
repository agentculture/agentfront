"""Unit tests for agentfront.taui.render.ansi — render_ansi."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.state import (
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
    """The status line appears at the end."""
    state = _build_state()
    output = render_ansi(state)
    assert "[info] Ready" in output


def test_hidden_panel_not_rendered() -> None:
    """A hidden panel's title does NOT appear in the output."""
    state = _build_state()
    output = render_ansi(state)
    assert "Feedback" not in output


def test_severity_and_message_in_status() -> None:
    """Status severity and message are rendered."""
    state = _build_state(severity="warning", message="Disk space low")
    output = render_ansi(state)
    assert "[warning] Disk space low" in output


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
