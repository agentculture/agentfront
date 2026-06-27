"""Unit tests for agentfront.taui.diagnose — cross-render invariant checker."""

from __future__ import annotations

from agentfront.taui.diagnose import (
    BUG_CLASSES,
    DiagnoseResult,
    Diagnosis,
    Finding,
    diagnose,
    diagnose_structured,
)
from agentfront.taui.mirror import serialize
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.state import (
    Action,
    Background,
    ConversationLine,
    Header,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
    WorkItem,
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


# ---------------------------------------------------------------------------
# Test 5: structured layer (Finding / Diagnosis / diagnose_structured)
# ---------------------------------------------------------------------------


class TestDiagnoseStructured:
    """diagnose_structured returns structured Diagnosis objects."""

    # --- clean states (must yield ok=True / empty findings) ---

    def test_bare_state_ok(self) -> None:
        diag = diagnose_structured(TAUIState())
        assert diag.ok is True
        assert diag.findings == []

    def test_clean_populated_state_ok(self) -> None:
        """Visible blocking popup + visible panel + WorkItem + error status → ok."""
        state = TAUIState(
            focused="tools.search",
            panels=[
                Panel(
                    id="panel.tools",
                    title="Tools",
                    visible=True,
                    items=[PanelItem(id="tools.search", label="Search", status="available")],
                )
            ],
            popups=[
                Popup(
                    id="popup.confirm",
                    kind="confirm",
                    visible=True,
                    blocking=True,
                    actions=[Action(selector="popup.confirm.yes", input="y", description="OK")],
                )
            ],
            work_item=WorkItem(task_id="t1", engine="claude"),
            status=Status(severity="error", message="Something failed"),
        )
        diag = diagnose_structured(state)
        assert diag.ok is True
        assert diag.findings == []

    # --- FOCUS finding ---

    def test_focus_finding_on_unresolvable(self) -> None:
        state = TAUIState(focused="nonexistent.xyz")
        diag = diagnose_structured(state)
        assert not diag.ok
        focus_findings = diag.by_class("FOCUS")
        assert len(focus_findings) > 0

    # --- INPUT_ROUTING finding ---

    def test_input_routing_finding_desynced_mirror(self) -> None:
        """A mirror with a bogus available_actions selector yields an INPUT_ROUTING finding."""
        state = TAUIState()
        bad_mirror = serialize(state)
        bad_mirror["available_actions"].append(
            {"selector": "bogus.selector.xyz", "input": "x", "description": "Bad"}
        )
        diag = diagnose_structured(state, mirror=bad_mirror)
        assert not diag.ok
        ir_findings = diag.by_class("INPUT_ROUTING")
        assert len(ir_findings) > 0
        assert any("bogus.selector.xyz" in f.message for f in ir_findings)

    # --- RENDER finding ---

    def test_render_finding_conversation_text_missing(self) -> None:
        """Stale renders that lack a conversation line's text yield RENDER findings."""
        state = TAUIState(
            conversation=[ConversationLine(text="hello world")],
        )
        # Empty strings represent renders that pre-date the conversation line.
        diag = diagnose_structured(state, ansi="", markdown="")
        assert not diag.ok
        render_findings = diag.by_class("RENDER")
        assert len(render_findings) > 0
        assert any("hello world" in f.message for f in render_findings)

    # --- THEME finding ---

    def test_theme_finding_semantic_without_theme(self) -> None:
        state = TAUIState(background=Background(semantic="x", theme=""))
        diag = diagnose_structured(state)
        assert not diag.ok
        theme_findings = diag.by_class("THEME")
        assert len(theme_findings) == 1
        assert "background.semantic set without a theme" in theme_findings[0].message

    # --- POPUP_LIFECYCLE finding ---

    def test_popup_lifecycle_blocking_not_visible(self) -> None:
        state = TAUIState(
            popups=[
                Popup(
                    id="popup.blocker",
                    kind="confirm",
                    blocking=True,
                    visible=False,
                )
            ]
        )
        diag = diagnose_structured(state)
        assert not diag.ok
        pl_findings = diag.by_class("POPUP_LIFECYCLE")
        assert len(pl_findings) == 1
        assert "popup.blocker" in pl_findings[0].message

    # --- LAYOUT finding ---

    def test_layout_finding_duplicate_panel_ids(self) -> None:
        state = TAUIState(
            panels=[
                Panel(id="panel.dup", title="A", visible=False, items=[]),
                Panel(id="panel.dup", title="B", visible=False, items=[]),
            ]
        )
        diag = diagnose_structured(state)
        assert not diag.ok
        layout_findings = diag.by_class("LAYOUT")
        assert len(layout_findings) > 0
        assert any("panel.dup" in f.message for f in layout_findings)

    # --- Diagnosis.to_dict() shape ---

    def test_diagnosis_to_dict_ok(self) -> None:
        diag = Diagnosis()
        d = diag.to_dict()
        assert d == {"ok": True, "findings": []}

    def test_diagnosis_to_dict_with_findings(self) -> None:
        f = Finding(bug_class="FOCUS", message="test msg")
        diag = Diagnosis(findings=[f])
        d = diag.to_dict()
        assert d["ok"] is False
        assert d["findings"] == [{"bug_class": "FOCUS", "message": "test msg"}]

    # --- by_class() filtering ---

    def test_by_class_filtering(self) -> None:
        findings = [
            Finding(bug_class="FOCUS", message="focus msg"),
            Finding(bug_class="RENDER", message="render msg"),
            Finding(bug_class="FOCUS", message="focus msg 2"),
        ]
        diag = Diagnosis(findings=findings)
        focus_only = diag.by_class("FOCUS")
        assert len(focus_only) == 2
        assert all(f.bug_class == "FOCUS" for f in focus_only)
        render_only = diag.by_class("RENDER")
        assert len(render_only) == 1

    # --- BUG_CLASSES completeness ---

    def test_all_bug_class_names_in_bug_classes(self) -> None:
        expected = {
            "STATE",
            "RENDER",
            "LAYOUT",
            "FOCUS",
            "INPUT_ROUTING",
            "THEME",
            "POPUP_LIFECYCLE",
        }
        assert expected <= set(BUG_CLASSES)
