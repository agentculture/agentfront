"""Unit tests for agentfront.taui.state — TAUIState dataclass tree."""

from __future__ import annotations

import json
from typing import Any

import pytest

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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _round_trip(state: TAUIState) -> TAUIState:
    """Serialize to dict and back; return the reconstructed state."""
    return TAUIState.from_dict(state.to_dict())


def _build_populated_state() -> TAUIState:
    """Return a representative TAUIState exercising every field."""
    return TAUIState(
        screen="main",
        mode="executing",
        focused="input.prompt",
        header=Header(title="MyApp", subtitle="v0.1.0", version="0.1.0"),
        zones={
            "top.status": Zone(visible=True),
            "left.skills": Zone(visible=True),
            "main.conversation": Zone(visible=True),
            "bottom.input": Zone(visible=False),
        },
        panels=[
            Panel(
                id="panel.search",
                title="Search",
                visible=True,
                content_summary="Search tools",
                items=[
                    PanelItem(
                        id="search.query",
                        label="Query",
                        status="available",
                        tags=["core"],
                    ),
                    PanelItem(
                        id="search.advanced",
                        label="Advanced",
                        status="disabled",
                        tags=["beta"],
                    ),
                ],
            ),
            Panel(
                id="panel.feedback",
                title="Feedback",
                visible=False,
                content_summary="Feedback tools",
                items=[
                    PanelItem(id="feedback.record", label="Record", status="available"),
                ],
            ),
        ],
        popups=[
            Popup(
                id="popup.confirm",
                kind="confirm",
                visible=True,
                blocking=True,
                opened_by="user",
                reason="action requested",
                message="Proceed?",
                actions=[
                    Action(selector="confirm.yes", input="y", description="Confirm"),
                    Action(selector="confirm.no", input="n", description="Cancel"),
                ],
                timeout_ms=30000,
            ),
        ],
        status=Status(severity="warning", message="Disk space low"),
        work_item=WorkItem(task_id="task-42", engine="local", step_count=3, running=True),
        problems=[{"code": "E001", "message": "example problem"}],
    )


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


def test_round_trip_populated_state() -> None:
    """from_dict(to_dict(s)) == s for a fully populated state."""
    state = _build_populated_state()
    assert _round_trip(state) == state


def test_round_trip_defaults() -> None:
    """Round-trip a default (empty) state."""
    state = TAUIState()
    assert _round_trip(state) == state


def test_round_trip_no_work_item() -> None:
    """State with work_item=None round-trips correctly."""
    state = TAUIState(work_item=None)
    assert _round_trip(state) == state


def test_round_trip_empty_collections() -> None:
    """State with empty panels/popups round-trips."""
    state = TAUIState(panels=[], popups=[])
    assert _round_trip(state) == state


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def test_to_dict_is_json_serializable() -> None:
    """json.dumps(state.to_dict()) never raises."""
    state = _build_populated_state()
    payload = json.dumps(state.to_dict())
    assert isinstance(payload, str)
    assert len(payload) > 0


def test_to_dict_contains_only_json_types() -> None:
    """to_dict produces only dict/list/str/int/float/bool/None."""

    def _check(obj: Any) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                _check(v)
        elif isinstance(obj, list):
            for item in obj:
                _check(item)
        elif not isinstance(obj, (str, int, float, bool, type(None))):
            pytest.fail(f"Non-JSON type in to_dict: {type(obj).__name__}: {obj!r}")

    _check(_build_populated_state().to_dict())


# ---------------------------------------------------------------------------
# Stable ids
# ---------------------------------------------------------------------------


def test_panel_has_stable_id() -> None:
    """Every Panel carries a string id."""
    panel = Panel(id="p1", title="Test")
    assert panel.id == "p1"


def test_panel_item_has_stable_id() -> None:
    """Every PanelItem carries a string id."""
    item = PanelItem(id="i1", label="Item")
    assert item.id == "i1"


def test_popup_has_stable_id() -> None:
    """Every Popup carries a string id."""
    popup = Popup(id="u1", kind="alert")
    assert popup.id == "u1"


def test_zone_keyed_by_name() -> None:
    """Zones are keyed by name in the zones dict."""
    state = TAUIState(zones={"top.status": Zone()})
    assert "top.status" in state.zones


# ---------------------------------------------------------------------------
# No view-specific fields
# ---------------------------------------------------------------------------


def test_state_has_no_view_specific_fields() -> None:
    """TAUIState fields are purely structural — no ansi/markdown/render hints."""
    field_names = {f.name for f in TAUIState.__dataclass_fields__.values()}
    view_keywords = {"ansi", "markdown", "render", "colors", "style", "format"}
    overlap = field_names & view_keywords
    assert not overlap, f"State has view-specific fields: {overlap}"


def test_panel_has_no_view_specific_fields() -> None:
    """Panel fields are purely structural."""
    field_names = {f.name for f in Panel.__dataclass_fields__.values()}
    view_keywords = {"ansi", "markdown", "render", "colors", "style", "format"}
    overlap = field_names & view_keywords
    assert not overlap, f"Panel has view-specific fields: {overlap}"


def test_popup_has_no_view_specific_fields() -> None:
    """Popup fields are purely structural."""
    field_names = {f.name for f in Popup.__dataclass_fields__.values()}
    view_keywords = {"ansi", "markdown", "render", "colors", "style", "format"}
    overlap = field_names & view_keywords
    assert not overlap, f"Popup has view-specific fields: {overlap}"


# ---------------------------------------------------------------------------
# work_item serialised under key "work"
# ---------------------------------------------------------------------------


def test_work_item_serialised_as_work() -> None:
    """work_item appears under the key 'work' in to_dict."""
    state = TAUIState(work_item=WorkItem(task_id="t1"))
    d = state.to_dict()
    assert "work" in d
    assert d["work"] is not None
    assert d["work"]["task_id"] == "t1"


def test_work_item_none_serialises_as_none() -> None:
    """When work_item is None, 'work' is None in the dict."""
    state = TAUIState(work_item=None)
    d = state.to_dict()
    assert d["work"] is None


# ---------------------------------------------------------------------------
# Default zones
# ---------------------------------------------------------------------------


def test_default_zones_present() -> None:
    """A default TAUIState has the four standard zones."""
    state = TAUIState()
    expected_keys = {"top.status", "left.skills", "main.conversation", "bottom.input"}
    assert set(state.zones.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Immutability / ownership of mutable defaults
# ---------------------------------------------------------------------------


def test_mutable_defaults_are_independent() -> None:
    """Two TAUIState instances own independent mutable collections."""
    s1 = TAUIState()
    s2 = TAUIState()
    s1.panels.append(Panel(id="p1"))
    assert len(s2.panels) == 0


def test_panel_items_independent() -> None:
    """Panel items lists are independent across instances."""
    p1 = Panel(id="a", items=[PanelItem(id="i1", label="L1")])
    p2 = Panel(id="b")
    p1.items.append(PanelItem(id="i2", label="L2"))
    assert len(p2.items) == 0


def test_popup_actions_independent() -> None:
    """Popup actions lists are independent across instances."""
    u1 = Popup(id="u1", kind="alert", actions=[Action(selector="s1", input="i")])
    u2 = Popup(id="u2", kind="alert")
    u1.actions.append(Action(selector="s2", input="j"))
    assert len(u2.actions) == 0
