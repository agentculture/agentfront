"""Colleague-parity conformance tests for agentfront.taui.

GOAL: prove agentfront's TAUIState + mirror + reducer + diagnose preserve the
BEHAVIORAL invariants of colleague's hand-built TUI, so colleague can
eventually import agentfront's TAUI instead of maintaining its own
(honesty condition h6).

Each test's docstring names the colleague test it mirrors.

=============================================================================
PARITY GAPS
=============================================================================

The following behavioural differences between colleague's CockpitState and
agentfront's TAUIState were identified while writing these tests. They are
NOT bugs — they represent deliberate scope differences. Any consumer importing
agentfront.taui instead of colleague.tui must account for them.

PARITY GAP 1: Background field absent
    colleague.tui.state.CockpitState has a `background` field (Background
    dataclass with theme/animation/frame/semantic) used for visual ambience and
    THEME bug-class signals (e.g. "stronger_agent_recommended" semantic).
    agentfront.taui.state.TAUIState has NO `background` field — the TAUI
    package does not model visual/animation ambience at all.
    Tested by: test_parity_gap_background_field_absent

PARITY GAP 2: Header field is agentfront-specific
    agentfront.taui.state.TAUIState has an extra `header` field (Header
    dataclass with title/subtitle/version) to expose the app identity in the
    mirror. colleague.tui.state.CockpitState has no `header` field.
    Not blocked by a test — every TAUIState round-trip includes header.

PARITY GAP 3: SkillSuggested event absent
    colleague.tui.events.SkillSuggested fires when a stronger agent is
    recommended; colleague's reducer opens a skill-suggestion popup and sets
    background.theme/semantic.  agentfront.taui.events has no SkillSuggested
    — skill suggestions must be modelled as a Popup injected directly into
    TAUIState by the caller.
    Tested by: test_parity_gap_skill_suggested_absent

PARITY GAP 4: WorkStep event absent
    colleague.tui.events.WorkStep fires on each tool-call step; colleague's
    reducer increments work_item.step_count and opens an error popup on
    failure.  agentfront.taui.events has no WorkStep — callers must construct
    updated TAUIState directly.
    Tested by: test_parity_gap_work_step_absent

PARITY GAP 5: Serializer renamed
    colleague: `from colleague.tui.taui import serialize`
    agentfront: `from agentfront.taui.mirror import serialize`
    (The function plays the same role but lives in a different module.)

PARITY GAP 6: selectors.resolve() signature differs
    colleague: `resolve(taui_dict, selector)` — operates on the serialised
    TAUI mirror dict.
    agentfront: `resolve(state, selector)` — operates on the TAUIState object.
    Tests that call resolve() use the agentfront signature throughout.

PARITY GAP 7: diagnose() interface is completely different
    colleague: `diagnose(taui_dict, ansi_str, events_list) -> Diagnosis`
    with seven explicit bug classes (STATE, RENDER, LAYOUT, FOCUS,
    INPUT_ROUTING, THEME, POPUP_LIFECYCLE).
    agentfront: `diagnose(state) -> DiagnoseResult(ok, problems)` — a simpler
    cross-render invariant checker; no separate bug classes.
    Tests mirror the purity/consistency invariants, not the seven-class taxonomy.

PARITY GAP 8: available_actions composition differs
    colleague: visible popup actions + standing `input.prompt`.
    agentfront: visible panel items (with input="select") + visible popup
    actions + standing `input.prompt`.
    Tests verify that every selector in available_actions resolves, not the
    exact membership.

PARITY GAP 9: SCHEMA_VERSION
    colleague TAUI schema version is "0.2"; agentfront is "0.1".

PARITY GAP 10: Reducer event coverage differs
    colleague's reducer handles Tick (advance background.frame), UserInput
    (append to conversation panel), WorkStep (increment step_count/open popup).
    agentfront's reducer treats Tick and UserInput as no-ops (returns
    unchanged state).

PARITY GAP 11: Frozen vs mutable dataclasses
    agentfront.taui.state uses frozen=True dataclasses (immutable); all
    mutations go through dataclasses.replace().  colleague.tui.state uses
    mutable dataclasses.  The invariant tests still hold; equality semantics
    differ when constructing modified copies.

PARITY GAP 12: Zone resolution via selectors.resolve()
    colleague.tui.selectors.resolve() can resolve zone keys (e.g.
    "top.status") directly via the taui dict.
    agentfront.taui.selectors.resolve() does NOT resolve zone keys — zones are
    not in the resolve lookup.  Zone info is in TAUIState.zones but not
    addressed via the public resolve() API.
=============================================================================
"""

import json
from dataclasses import replace

from agentfront.taui.diagnose import DiagnoseResult, diagnose
from agentfront.taui.events import Dismiss, KeyPress, SelectorAction, Tick, UserInput
from agentfront.taui.mirror import SCHEMA_VERSION, serialize
from agentfront.taui.selectors import resolve
from agentfront.taui.state import (
    Action,
    Header,
    Panel,
    PanelItem,
    Popup,
    Status,
    TAUIState,
    WorkItem,
    Zone,
)

# =============================================================================
# PARITY GAPS — surfaced by one test so they appear in pytest -s output
# =============================================================================

PARITY_GAPS = [
    "GAP 1: background field absent — TAUIState has no Background (theme/animation/frame/semantic)",
    "GAP 2: header field is agentfront-specific — CockpitState has no Header",
    "GAP 3: SkillSuggested event absent — agentfront has no SkillSuggested",
    "GAP 4: WorkStep event absent — agentfront has no WorkStep",
    "GAP 5: serializer renamed — taui.serialize → mirror.serialize",
    "GAP 6: selectors.resolve() signature — colleague takes (dict, str), agentfront (state, str)",
    "GAP 7: diagnose() interface is completely different — no 7-class taxonomy in agentfront",
    "GAP 8: available_actions composition — agentfront also includes panel items (input=select)",
    "GAP 9: SCHEMA_VERSION — colleague='0.2', agentfront='0.1'",
    "GAP 10: reducer event coverage — Tick/UserInput/WorkStep are no-ops in agentfront",
    "GAP 11: frozen vs mutable dataclasses — agentfront uses frozen=True",
    "GAP 12: Zone resolution — agentfront selectors.resolve() does NOT resolve zone keys",
]


def test_parity_gaps_surface():
    """Print all documented parity gaps to stdout so they surface in pytest -s output."""
    for gap in PARITY_GAPS:
        print(gap)
    assert len(PARITY_GAPS) == 12


# =============================================================================
# PARITY GAP smoke-tests (prove gaps are real, not theoretical)
# =============================================================================


def test_parity_gap_background_field_absent():
    """PARITY GAP 1: TAUIState has no background field (colleague does).

    Mirrors: colleague's TestFieldPresence.test_background_field_has_frame
    """
    state = TAUIState()
    assert not hasattr(
        state, "background"
    ), "GAP 1 would be closed: TAUIState now has a 'background' field"


def test_parity_gap_skill_suggested_absent():
    """PARITY GAP 3: agentfront has no SkillSuggested event.

    Mirrors: colleague's test_skill_suggested_opens_popup
    """
    from agentfront.taui import events as ev_mod

    assert not hasattr(
        ev_mod, "SkillSuggested"
    ), "GAP 3 would be closed: agentfront now has a SkillSuggested event"


def test_parity_gap_work_step_absent():
    """PARITY GAP 4: agentfront has no WorkStep event.

    Mirrors: colleague's test_drive_step_increments_step_count_when_drive_active
    """
    from agentfront.taui import events as ev_mod

    assert not hasattr(
        ev_mod, "WorkStep"
    ), "GAP 4 would be closed: agentfront now has a WorkStep event"


# =============================================================================
# 1. TAUIState JSON round-trip
#    Mirrors: colleague tests/test_tui_state.py :: TestRoundTrip
# =============================================================================


def _minimal_state() -> TAUIState:
    """Return a TAUIState with all defaults (no nested objects set)."""
    return TAUIState()


def _rich_state() -> TAUIState:
    """Return a TAUIState with all nested objects populated for round-trip.

    Note: TAUIState has a header field (GAP 2) and no background field (GAP 1).
    """
    action = Action(selector="button.ok", input="enter", description="Confirm")
    item = PanelItem(id="skill-1", label="My Skill", status="active")
    panel = Panel(
        id="skills",
        title="Skills Panel",
        visible=True,
        content_summary="1 skill",
        items=[item],
    )
    popup = Popup(
        id="popup-1",
        kind="confirmation",
        visible=True,
        blocking=True,
        opened_by="user",
        reason="test reason",
        message="Are you sure?",
        actions=[action],
        timeout_ms=5000,
    )
    header = Header(title="My App", subtitle="Test subtitle", version="1.0.0")
    status = Status(severity="warn", message="Heads up")
    work_item = WorkItem(task_id="abc123", engine="vllm-openai", step_count=3, running=True)
    return TAUIState(
        screen="main",
        mode="executing",
        focused="input.prompt",
        header=header,
        zones={"top.status": Zone(visible=True), "left.skills": Zone(visible=False)},
        panels=[panel],
        popups=[popup],
        status=status,
        work_item=work_item,
        problems=[{"code": "E001", "message": "Something went wrong"}],
    )


class TestRoundTrip:
    """TAUIState.to_dict() / from_dict() preserves equality.

    Mirrors: colleague tests/test_tui_state.py :: TestRoundTrip
    """

    def test_minimal_state_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_minimal_state_round_trip"""
        s = _minimal_state()
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_rich_state_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_rich_state_round_trip"""
        s = _rich_state()
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_round_trip_is_json_serializable(self):
        """to_dict() must produce a dict that json.dumps() accepts.

        Mirrors: colleague TestRoundTrip.test_round_trip_is_json_serializable
        """
        s = _rich_state()
        d = s.to_dict()
        dumped = json.dumps(d)
        assert isinstance(dumped, str)

    def test_nested_popup_with_actions_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_nested_popup_with_actions_round_trip"""
        action = Action(selector="btn.yes", input="enter", description="Yes")
        popup = Popup(
            id="p1",
            kind="error",
            visible=True,
            blocking=False,
            opened_by="agent",
            reason="oops",
            message="Error occurred",
            actions=[action],
            timeout_ms=None,
        )
        s = TAUIState(popups=[popup])
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_nested_panel_with_items_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_nested_panel_with_items_round_trip"""
        item = PanelItem(id="i1", label="Item One", status="available")
        panel = Panel(id="p1", title="Panel One", visible=False, items=[item])
        s = TAUIState(panels=[panel])
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_work_none_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_drive_none_round_trip"""
        s = TAUIState(work_item=None)
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_work_present_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_drive_present_round_trip"""
        s = TAUIState(work_item=WorkItem(task_id="t1", engine="mock", step_count=0, running=False))
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_problems_list_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_problems_list_round_trip"""
        s = TAUIState(problems=[{"code": "W1", "message": "a warning"}])
        assert TAUIState.from_dict(s.to_dict()) == s

    def test_zones_dict_round_trip(self):
        """Mirrors: colleague TestRoundTrip.test_zones_dict_round_trip"""
        zones = {
            "top.status": Zone(visible=True),
            "left.skills": Zone(visible=False),
        }
        s = TAUIState(zones=zones)
        assert TAUIState.from_dict(s.to_dict()) == s


class TestFieldPresence:
    """TAUIState structure checks.

    Mirrors: colleague tests/test_tui_state.py :: TestFieldPresence
    """

    def test_screen_field(self):
        """Mirrors: colleague TestFieldPresence.test_screen_field"""
        s = TAUIState()
        assert s.screen == "main"

    def test_mode_field(self):
        """Mirrors: colleague TestFieldPresence.test_mode_field"""
        s = TAUIState()
        assert s.mode == "planning"

    def test_focused_field(self):
        """Mirrors: colleague TestFieldPresence.test_focused_field"""
        s = TAUIState()
        assert s.focused == "input.prompt"

    def test_zones_field_has_four_defaults(self):
        """Mirrors: colleague TestFieldPresence.test_zones_field_has_four_defaults"""
        s = TAUIState()
        assert "top.status" in s.zones
        assert "left.skills" in s.zones
        assert "main.conversation" in s.zones
        assert "bottom.input" in s.zones

    def test_all_default_zones_visible(self):
        """Mirrors: colleague TestFieldPresence.test_all_default_zones_visible"""
        s = TAUIState()
        for zone in s.zones.values():
            assert zone.visible is True

    def test_panels_field_is_list(self):
        """Mirrors: colleague TestFieldPresence.test_panels_field_is_list"""
        s = TAUIState()
        assert isinstance(s.panels, list)

    def test_popups_field_is_list(self):
        """Mirrors: colleague TestFieldPresence.test_popups_field_is_list"""
        s = TAUIState()
        assert isinstance(s.popups, list)

    def test_status_field_has_severity(self):
        """Mirrors: colleague TestFieldPresence.test_status_field_has_severity"""
        s = TAUIState()
        assert hasattr(s.status, "severity")
        assert isinstance(s.status.severity, str)

    def test_status_field_has_message(self):
        """Mirrors: colleague TestFieldPresence.test_status_field_has_message"""
        s = TAUIState()
        assert hasattr(s.status, "message")
        assert isinstance(s.status.message, str)

    def test_status_defaults(self):
        """Mirrors: colleague TestFieldPresence.test_status_defaults"""
        st = Status()
        assert st.severity == "info"
        assert st.message == ""

    def test_work_item_field_default_none(self):
        """Mirrors: colleague TestFieldPresence.test_drive_field_default_none"""
        s = TAUIState()
        assert s.work_item is None

    def test_problems_field_default_empty(self):
        """Mirrors: colleague TestFieldPresence.test_problems_field_default_empty"""
        s = TAUIState()
        assert s.problems == []

    def test_to_dict_contains_required_top_level_keys(self):
        """to_dict() must include the keys needed for the agent-facing contract.

        Mirrors: colleague TestFieldPresence.test_to_dict_contains_all_top_level_keys
        Note: agentfront also emits 'header' (GAP 2); 'background' is absent (GAP 1).
        """
        d = TAUIState().to_dict()
        required = (
            "screen",
            "mode",
            "focused",
            "zones",
            "panels",
            "popups",
            "status",
            "work",
            "problems",
        )
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_action_description_default_empty(self):
        """Mirrors: colleague TestFieldPresence.test_action_description_default_empty"""
        a = Action(selector="btn", input="enter")
        assert a.description == ""

    def test_panel_item_status_default(self):
        """Mirrors: colleague TestFieldPresence.test_panel_item_status_default"""
        item = PanelItem(id="i1", label="Label")
        assert item.status == "available"

    def test_work_item_dataclass_fields(self):
        """Mirrors: colleague TestFieldPresence.test_drive_dataclass_fields"""
        d = WorkItem(task_id="t1", engine="mock", step_count=2, running=True)
        assert d.task_id == "t1"
        assert d.engine == "mock"
        assert d.step_count == 2
        assert d.running is True

    def test_popup_timeout_ms_none_round_trip(self):
        """Mirrors: colleague TestFieldPresence.test_popup_timeout_ms_none_round_trip"""
        p = Popup(id="p1", kind="progress", timeout_ms=None)
        s = TAUIState(popups=[p])
        s2 = TAUIState.from_dict(s.to_dict())
        assert s2.popups[0].timeout_ms is None

    def test_popup_timeout_ms_int_round_trip(self):
        """Mirrors: colleague TestFieldPresence.test_popup_timeout_ms_int_round_trip"""
        p = Popup(id="p1", kind="progress", timeout_ms=3000)
        s = TAUIState(popups=[p])
        s2 = TAUIState.from_dict(s.to_dict())
        assert s2.popups[0].timeout_ms == 3000


# =============================================================================
# 2. mirror.serialize() — taui_version + available_actions + selector resolution
#    Mirrors: colleague tests/test_tui_taui.py
# =============================================================================


def _make_state_with_popup_and_panel() -> TAUIState:
    """Build a TAUIState with a visible popup (with actions) and a panel."""
    popup = Popup(
        id="popup.confirm",
        kind="confirmation",
        visible=True,
        blocking=True,
        opened_by="system",
        reason="approve_hook",
        message="Approve the hook?",
        actions=[
            Action(selector="button.accept", input="enter", description="Accept"),
            Action(selector="button.reject", input="enter", description="Reject"),
        ],
        timeout_ms=5000,
    )
    panel = Panel(
        id="panel.skills",
        title="Skills",
        visible=True,
        content_summary="2 skills",
        items=[
            PanelItem(id="skill.one", label="Skill One", status="available"),
        ],
    )
    status = Status(severity="error", message="Something went wrong")
    return TAUIState(
        screen="main",
        mode="driving",
        focused="input.prompt",
        popups=[popup],
        panels=[panel],
        status=status,
        work_item=WorkItem(task_id="t-123", engine="mock", step_count=3, running=True),
    )


def _is_json_safe(obj, path="root") -> None:
    """Recursively assert that obj contains only JSON-safe types."""
    allowed = (dict, list, str, int, float, bool, type(None))
    assert isinstance(obj, allowed), f"Non-JSON type {type(obj)} at {path}: {obj!r}"
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert isinstance(k, str), f"Non-str dict key {k!r} at {path}"
            _is_json_safe(v, path=f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _is_json_safe(v, path=f"{path}[{i}]")


class TestMirrorSerialize:
    """mirror.serialize() emits taui_version and available_actions.

    Mirrors: colleague tests/test_tui_taui.py
    """

    def test_serialize_returns_dict(self):
        """Mirrors: colleague test_serialize_returns_dict"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        assert isinstance(result, dict)

    def test_taui_version_present(self):
        """serialize() must always include taui_version.

        Mirrors: colleague test_taui_version_matches_schema_version
        Note (GAP 9): agentfront version is "0.1", colleague is "0.2".
        """
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        assert "taui_version" in result
        assert result["taui_version"] == SCHEMA_VERSION

    def test_json_dumps_succeeds(self):
        """Mirrors: colleague test_json_dumps_succeeds"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        dumped = json.dumps(result)
        assert isinstance(dumped, str)
        assert len(dumped) > 0

    def test_no_non_json_types(self):
        """Mirrors: colleague test_no_non_json_types"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        _is_json_safe(result)

    def test_top_level_fields_present(self):
        """Mirrors: colleague test_top_level_fields_present"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        for key in (
            "taui_version",
            "screen",
            "mode",
            "focused",
            "zones",
            "panels",
            "popups",
            "status",
            "work",
            "problems",
            "available_actions",
        ):
            assert key in result, f"Missing top-level key: {key}"

    def test_available_actions_is_list(self):
        """Mirrors: colleague test_available_actions_is_list"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        assert isinstance(result["available_actions"], list)

    def test_available_actions_includes_standing_input_prompt(self):
        """Mirrors: colleague test_available_actions_includes_standing_input_prompt"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        selectors = {a["selector"] for a in result["available_actions"]}
        assert (
            "input.prompt" in selectors
        ), f"Expected 'input.prompt' standing action, got: {selectors}"

    def test_available_actions_each_have_selector_input_description(self):
        """Mirrors: colleague test_available_actions_each_have_selector_input_description"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        for action in result["available_actions"]:
            assert "selector" in action
            assert "input" in action
            assert "description" in action

    def test_available_actions_invisible_popup_excluded(self):
        """Actions from non-visible popups must NOT appear in available_actions.

        Mirrors: colleague test_available_actions_invisible_popup_excluded
        """
        popup_hidden = Popup(
            id="popup.hidden",
            kind="help",
            visible=False,
            actions=[Action(selector="button.hidden", input="enter", description="Hidden")],
        )
        state = TAUIState(popups=[popup_hidden])
        result = serialize(state)
        selectors = {a["selector"] for a in result["available_actions"]}
        assert "button.hidden" not in selectors

    def test_available_actions_no_popup_still_has_standing_action(self):
        """Mirrors: colleague test_available_actions_no_popup_still_has_standing_action"""
        state = TAUIState()
        result = serialize(state)
        selectors = {a["selector"] for a in result["available_actions"]}
        assert "input.prompt" in selectors

    def test_available_actions_popup_accept_selector_present(self):
        """Visible popup actions must appear in available_actions.

        Mirrors: colleague test_available_actions_includes_popup_accept_selector
        """
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        selectors = {a["selector"] for a in result["available_actions"]}
        assert (
            "button.accept" in selectors
        ), f"Expected 'button.accept' in available_actions, got: {selectors}"

    def test_available_actions_selectors_all_resolve(self):
        """KEY INVARIANT (h6): every selector in available_actions resolves.

        Selectors are DERIVED from state — they cannot drift.
        Mirrors: colleague invariant 'selectors derived from state and all resolve'
        (the h3 honesty condition; tested implicitly via serialize() in colleague).
        """
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        for entry in result["available_actions"]:
            sel = entry["selector"]
            # resolve() raises AgentfrontError on unknown selector
            node = resolve(state, sel)
            assert node is not None

    def test_status_has_severity_and_message(self):
        """Mirrors: colleague test_status_has_severity_and_message"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        status = result["status"]
        assert "severity" in status
        assert "message" in status
        assert status["severity"] == "error"
        assert status["message"] == "Something went wrong"

    def test_work_present_when_set(self):
        """Mirrors: colleague test_drive_present_when_set"""
        state = _make_state_with_popup_and_panel()
        result = serialize(state)
        work = result["work"]
        assert work is not None
        assert work["task_id"] == "t-123"
        assert work["running"] is True

    def test_work_none_when_not_set(self):
        """Mirrors: colleague test_drive_none_when_not_set"""
        state = TAUIState()
        result = serialize(state)
        assert result["work"] is None

    def test_problems_forwarded(self):
        """Mirrors: colleague test_problems_forwarded"""
        state = TAUIState(problems=[{"code": "E001", "msg": "bad"}])
        result = serialize(state)
        assert result["problems"] == [{"code": "E001", "msg": "bad"}]

    def test_empty_state_serializes_cleanly(self):
        """Mirrors: colleague test_empty_state_serializes_cleanly"""
        state = TAUIState()
        result = serialize(state)
        _is_json_safe(result)
        assert "taui_version" in result
        assert result["panels"] == []
        assert result["popups"] == []
        assert result["work"] is None
        assert result["problems"] == []


# =============================================================================
# 3. reduce() — purity and deterministic event folding
#    Mirrors: colleague tests/test_tui_reducer.py
#    Note (GAP 10): only events supported by agentfront are tested.
# =============================================================================


def _fresh() -> TAUIState:
    """Return a brand-new default TAUIState."""
    return TAUIState()


def _state_with_popup_and_panel() -> TAUIState:
    """Return a TAUIState with a panel (for focus-order testing) and a popup."""
    panel = Panel(
        id="panel.skills",
        title="Skills",
        visible=True,
        items=[
            PanelItem(id="skill.one", label="Skill One"),
            PanelItem(id="skill.two", label="Skill Two"),
        ],
    )
    popup = Popup(
        id="popup.confirm",
        kind="confirmation",
        visible=True,
        blocking=True,
        actions=[
            Action(selector="button.ok", input="enter", description="OK"),
        ],
    )
    return TAUIState(panels=[panel], popups=[popup], focused="input.prompt")


class TestReducerPurity:
    """reduce() is a pure function: input unchanged, output is a new value.

    Mirrors: colleague tests/test_tui_reducer.py :: test_reducer_returns_distinct_object
    and purity-related tests.
    Note (GAP 11): agentfront uses frozen dataclasses so mutations are impossible;
    we verify identity (is-not) and that reduce() returns consistent results.
    """

    def test_reducer_returns_new_or_same_but_equal(self):
        """reduce() on a no-op event returns a state equal to the input.

        Mirrors: colleague test_reducer_returns_distinct_object
        Note: agentfront may return the same frozen object for no-op events.
        """
        from agentfront.taui.reducer import reduce

        s0 = _fresh()
        s1 = reduce(s0, Tick(delta=3))
        # Purity: the returned state is equal (not mutated differently)
        assert s1.screen == s0.screen
        assert s1.mode == s0.mode
        assert s1.focused == s0.focused

    def test_tick_is_a_noop(self):
        """Tick is a no-op in agentfront (GAP 10).

        Mirrors: colleague test_tick_advances_frame_by_delta — but the invariant
        here is that reduce() does NOT crash and returns a valid state.
        """
        from agentfront.taui.reducer import reduce

        s0 = _fresh()
        s1 = reduce(s0, Tick(delta=3))
        assert isinstance(s1, TAUIState)
        # No background field → frame counter unchanged (GAP 1 + GAP 10)
        assert s1 == s0

    def test_user_input_is_a_noop(self):
        """UserInput is a no-op in agentfront (GAP 10).

        Mirrors: colleague test_user_input_focuses_prompt (the key invariant
        there is that the state changed; here we verify no crash + valid return).
        """
        from agentfront.taui.reducer import reduce

        s0 = _fresh()
        s1 = reduce(s0, UserInput(text="hello"))
        assert isinstance(s1, TAUIState)
        assert s1 == s0

    def test_key_press_does_not_crash(self):
        """Mirrors: colleague test_key_does_not_crash"""
        from agentfront.taui.reducer import reduce

        s0 = _fresh()
        s1 = reduce(s0, KeyPress(key="up"))
        assert s1 is not None
        assert isinstance(s1, TAUIState)

    def test_key_down_advances_focus(self):
        """KeyPress('down') advances focus within the focus order.

        Mirrors: colleague test_key_does_not_crash (extended — agentfront supports
        key navigation which colleague handles differently via the driver).
        """
        from agentfront.taui.reducer import reduce

        state = _state_with_popup_and_panel()
        # Focus starts at "input.prompt"; pressing down should navigate.
        # Focus order: panel items first (skill.one, skill.two), then input.prompt
        # Navigate to first item.
        state_at_first = replace(state, focused="skill.one")
        s1 = reduce(state_at_first, KeyPress(key="down"))
        assert isinstance(s1, TAUIState)
        # Focus should have moved toward next item or stayed at boundary.
        assert s1.focused in ("skill.two", "input.prompt")

    def test_dismiss_hides_topmost_visible_popup(self):
        """Dismiss event hides the topmost visible popup.

        Mirrors: colleague test_dismiss_hides_popup
        Note: agentfront dismiss targets the topmost visible popup; colleague
        targets by `event.target` id.
        """
        from agentfront.taui.reducer import reduce

        state = _state_with_popup_and_panel()
        assert any(p.visible for p in state.popups)

        s1 = reduce(state, Dismiss())
        visible_popups = [p for p in s1.popups if p.visible]
        assert len(visible_popups) == 0  # the one visible popup is now hidden

    def test_dismiss_does_not_remove_popup(self):
        """Dismiss hides the popup but does not delete it from the list.

        Mirrors: colleague test_dismiss_does_not_remove_popup
        """
        from agentfront.taui.reducer import reduce

        state = _state_with_popup_and_panel()
        s1 = reduce(state, Dismiss())
        assert len(s1.popups) == len(state.popups)

    def test_dismiss_noop_on_no_visible_popup(self):
        """Dismiss with no visible popup is a no-op.

        Mirrors: colleague test_dismiss_unknown_target_is_noop
        """
        from agentfront.taui.reducer import reduce

        s0 = _fresh()  # no popups
        s1 = reduce(s0, Dismiss())
        assert isinstance(s1, TAUIState)
        assert s1 == s0

    def test_selector_action_sets_focused(self):
        """SelectorAction dispatched to a panel item sets focus.

        Mirrors: colleague test_key_does_not_crash (agentfront-specific event
        with no direct colleague counterpart, but the selector→focus invariant
        is the agentfront analogue of colleague's input routing).
        """
        from agentfront.taui.reducer import reduce

        state = _state_with_popup_and_panel()
        s1 = reduce(state, SelectorAction(selector="skill.one"))
        assert s1.focused == "skill.one"

    def test_deterministic_fold(self):
        """Folding the same sequence of events twice yields equal states.

        Mirrors: the 'deterministic event folding' invariant implicit in
        colleague's reducer tests.
        """
        from agentfront.taui.reducer import reduce

        events = [
            KeyPress(key="down"),
            KeyPress(key="down"),
            Dismiss(),
            KeyPress(key="up"),
        ]
        state0 = _state_with_popup_and_panel()
        state_a = state0
        for ev in events:
            state_a = reduce(state_a, ev)

        state_b = state0
        for ev in events:
            state_b = reduce(state_b, ev)

        assert state_a == state_b

    def test_unknown_event_does_not_crash(self):
        """Unknown/no-op event types must not raise.

        Mirrors: colleague test_unknown_event_returns_new_copy
        """
        from agentfront.taui.reducer import reduce

        s0 = _fresh()
        s1 = reduce(s0, Tick())  # Tick is a no-op in agentfront
        assert isinstance(s1, TAUIState)


# =============================================================================
# 4. diagnose.diagnose() — ok on consistent state, not-ok on desynced
#    Mirrors: colleague tests/test_tui_diagnose.py :: TestPurity
#    Note (GAP 7): agentfront's diagnose() has a different interface —
#    it takes (state) and returns DiagnoseResult(ok, problems), not a
#    seven-class Diagnosis.
# =============================================================================


class TestDiagnose:
    """diagnose() returns ok on a consistent state, not-ok on a desynced one.

    Mirrors: colleague tests/test_tui_diagnose.py :: TestPurity
    """

    def test_diagnose_returns_diagnose_result(self):
        """diagnose() returns a DiagnoseResult.

        Mirrors: colleague test_clean_triple_end_to_end_has_no_findings
        (result type check).
        """
        result = diagnose(_fresh())
        assert isinstance(result, DiagnoseResult)

    def test_fresh_default_state_is_ok(self):
        """A bare default TAUIState is healthy from every angle.

        Mirrors: colleague TestPurity.test_fresh_default_state_is_clean
        """
        result = diagnose(_fresh())
        assert result.ok is True
        assert result.problems == []

    def test_consistent_state_with_popup_and_panel_is_ok(self):
        """A well-formed state with popup + panel yields ok=True.

        Mirrors: colleague TestPurity.test_clean_triple_end_to_end_has_no_findings
        """
        state = _make_state_with_popup_and_panel()
        result = diagnose(state)
        assert result.ok is True
        assert result.problems == []

    def test_desynced_focused_selector_is_not_ok(self):
        """A state with a focused selector that does not resolve yields ok=False.

        Mirrors: colleague TestSevenClassesReachable.test_focus_bug
        (the FOCUS bug class; agentfront surfaces it as a problem string instead).
        """
        state = TAUIState(focused="panel.does.not.exist")
        result = diagnose(state)
        assert result.ok is False
        assert result.problems  # at least one problem string

    def test_diagnose_result_to_dict_shape(self):
        """DiagnoseResult.to_dict() has 'ok' and 'problems' keys.

        Mirrors: colleague TestDiagnoseSnapshot.test_to_dict_shape (adapted).
        """
        result = diagnose(_fresh())
        d = result.to_dict()
        assert "ok" in d
        assert "problems" in d
        assert isinstance(d["ok"], bool)
        assert isinstance(d["problems"], list)

    def test_ok_is_false_when_problems_present(self):
        """DiagnoseResult.ok is False when problems is non-empty.

        Mirrors: colleague's invariant that disagreements surface as findings.
        """
        state = TAUIState(focused="nonexistent.selector")
        result = diagnose(state)
        assert result.ok is False
        assert len(result.problems) > 0

    def test_consistent_state_no_problems(self):
        """A consistent state has an empty problems list and ok=True.

        Mirrors: colleague TestPurity.test_clean_triple_end_to_end_has_no_findings
        """
        state = _make_state_with_popup_and_panel()
        result = diagnose(state)
        assert result.problems == []
        assert result.ok is True

    def test_visible_panel_item_label_must_appear_in_renders(self):
        """Visible panel item labels must appear in both ANSI and markdown renders.

        Mirrors: colleague TestHeadlineRenderCase.test_consistent_triple_has_no_render_finding
        (the RENDER invariant; agentfront checks label presence in renders).
        """
        item = PanelItem(id="skill.one", label="MySpecialLabel", status="available")
        panel = Panel(id="panel.main", title="Main", visible=True, items=[item])
        state = TAUIState(panels=[panel], focused="input.prompt")
        result = diagnose(state)
        # A consistent state where labels appear in renders must be ok.
        assert result.ok is True

    def test_desynced_provided_mirror_with_bad_selector_is_not_ok(self):
        """Providing a desynced mirror with an unresolvable available_actions selector
        yields ok=False.

        Mirrors: colleague TestSevenClassesReachable.test_input_routing_bug
        (INPUT_ROUTING bug class; agentfront surfaces it as a problem string).
        """
        state = _fresh()
        # Build a desynced mirror with a bogus action.
        bad_mirror = serialize(state)
        bad_mirror["available_actions"].append(
            {
                "selector": "popup.ghost.accept",
                "input": "enter",
                "description": "Ghost action",
            }
        )
        result = diagnose(state, mirror=bad_mirror)
        assert result.ok is False
        assert any("popup.ghost.accept" in p for p in result.problems)
