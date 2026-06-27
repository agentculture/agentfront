"""Unit tests for agentfront.taui.diagnose — cross-render invariant checker."""

from __future__ import annotations

from agentfront.taui.diagnose import DiagnoseResult, diagnose
from agentfront.taui.mirror import serialize
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.state import (
    Action,
    Header,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _populated_state() -> TAUIState:
    """A representative state with panels, a visible popup, and a focused item."""
    return TAUIState(
        header=Header(title="TestApp", version="0.1"),
        focused="tools.search",
        panels=[
            Panel(
                id="panel.tools",
                title="Tools",
                visible=True,
                items=[
                    PanelItem(id="tools.search", label="Search", status="available"),
                    PanelItem(id="tools.deploy", label="Deploy", status="available"),
                ],
            ),
        ],
        popups=[
            Popup(
                id="popup.confirm",
                kind="confirm",
                visible=True,
                blocking=True,
                actions=[
                    Action(selector="confirm.yes", input="y", description="Confirm"),
                ],
            ),
        ],
        status=Status(severity="info", message="Ready"),
    )


# ---------------------------------------------------------------------------
# Test 1: ok=True for a consistent state
# ---------------------------------------------------------------------------


class TestDiagnoseOk:
    """diagnose(state) returns ok=True when all renders agree."""

    def test_populated_state_ok(self) -> None:
        state = _populated_state()
        result = diagnose(state)
        assert result.ok is True
        assert result.problems == []

    def test_to_dict(self) -> None:
        result = DiagnoseResult(ok=True, problems=[])
        d = result.to_dict()
        assert d == {"ok": True, "problems": []}

    def test_to_dict_with_problems(self) -> None:
        result = DiagnoseResult(ok=False, problems=["something wrong"])
        d = result.to_dict()
        assert d == {"ok": False, "problems": ["something wrong"]}


# ---------------------------------------------------------------------------
# Test 2: detect desync via injected ANSI
# ---------------------------------------------------------------------------


class TestDiagnoseDesync:
    """diagnose detects disagreement when a render is desynced."""

    def test_ansi_desync_detects_missing_label(self) -> None:
        """Inject ANSI from a state with different visible items."""
        state = _populated_state()

        # other_state has a different visible item label ("OtherLabel")
        other_state = TAUIState(
            header=Header(title="OtherApp"),
            focused="other.item",
            panels=[
                Panel(
                    id="panel.other",
                    title="Other",
                    visible=True,
                    items=[
                        PanelItem(id="other.item", label="OtherLabel", status="available"),
                    ],
                ),
            ],
            status=Status(severity="info", message="Ready"),
        )

        desynced_ansi = render_ansi(other_state)
        result = diagnose(state, ansi=desynced_ansi)

        assert result.ok is False
        assert len(result.problems) > 0

        # At least one visible item's label is missing from the injected ANSI.
        problem_labels = {p for p in result.problems if "missing from ANSI" in p}
        assert len(problem_labels) > 0

    def test_markdown_desync_detects_missing_label(self) -> None:
        """Inject markdown from a state with different visible items."""
        state = _populated_state()

        other_state = TAUIState(
            header=Header(title="OtherApp"),
            focused="other.item",
            panels=[
                Panel(
                    id="panel.other",
                    title="Other",
                    visible=True,
                    items=[
                        PanelItem(id="other.item", label="OtherLabel", status="available"),
                    ],
                ),
            ],
            status=Status(severity="info", message="Ready"),
        )

        desynced_markdown = render_markdown(other_state)
        result = diagnose(state, markdown=desynced_markdown)

        assert result.ok is False
        assert len(result.problems) > 0

        problem_labels = {p for p in result.problems if "missing from markdown" in p}
        assert len(problem_labels) > 0


# ---------------------------------------------------------------------------
# Test 3: mirror desync
# ---------------------------------------------------------------------------


class TestDiagnoseMirrorDesync:
    """diagnose detects a mirror with an unresolvable selector."""

    def test_bad_selector_in_mirror(self) -> None:
        state = _populated_state()
        bad_mirror = serialize(state)
        bad_mirror["available_actions"].append(
            {"selector": "nonexistent.selector", "input": "x", "description": "Bad"}
        )
        result = diagnose(state, mirror=bad_mirror)
        assert result.ok is False
        assert any("nonexistent.selector" in p for p in result.problems)


# ---------------------------------------------------------------------------
# Test 4: focused selector check
# ---------------------------------------------------------------------------


class TestDiagnoseFocused:
    """diagnose checks the focused selector resolves."""

    def test_focused_resolves(self) -> None:
        state = _populated_state()
        result = diagnose(state)
        assert result.ok is True

    def test_focused_does_not_resolve(self) -> None:
        state = TAUIState(
            header=Header(title="TestApp", version="0.1"),
            focused="nonexistent.focus",
            panels=[
                Panel(
                    id="panel.tools",
                    title="Tools",
                    visible=True,
                    items=[
                        PanelItem(id="tools.search", label="Search", status="available"),
                    ],
                ),
            ],
            status=Status(severity="info", message="Ready"),
        )
        result = diagnose(state)
        assert result.ok is False
        assert any("Focused selector" in p for p in result.problems)
