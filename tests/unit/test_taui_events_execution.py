"""Unit tests for the TAUI execution events — ToolInvoked / ToolResult.

Covers: exact dataclass shapes (frozen, ClassVar type discriminator),
to_dict/from_dict round-trips (including non-empty args/error payloads and
defaults), registration in _REGISTRY and the Event union, dumps_events /
loads_events JSONL round-trips, event_from_dict's unknown-type error message,
and a lock-in test for SelectorAction.args round-tripping through the JSONL
helpers (SelectorAction itself is unchanged by this task).
"""

from __future__ import annotations

import pytest

from agentfront.taui.events import (
    _REGISTRY,
    Dismiss,
    Event,
    KeyPress,
    SelectorAction,
    Tick,
    ToolInvoked,
    ToolResult,
    UserInput,
    dumps_events,
    event_from_dict,
    loads_events,
)

# ---------------------------------------------------------------------------
# ToolInvoked
# ---------------------------------------------------------------------------


def test_tool_invoked_type_discriminator() -> None:
    assert ToolInvoked.type == "tool_invoked"
    assert ToolInvoked(selector="feedback.record").type == "tool_invoked"


def test_tool_invoked_defaults() -> None:
    ev = ToolInvoked(selector="feedback.record")
    assert ev.selector == "feedback.record"
    assert ev.args == {}


def test_tool_invoked_is_frozen() -> None:
    ev = ToolInvoked(selector="feedback.record")
    with pytest.raises(AttributeError):
        ev.selector = "other"  # type: ignore[misc]


def test_tool_invoked_round_trip_defaults() -> None:
    ev = ToolInvoked(selector="feedback.record")
    assert ToolInvoked.from_dict(ev.to_dict()) == ev


def test_tool_invoked_round_trip_with_args() -> None:
    ev = ToolInvoked(selector="feedback.record", args={"rating": 5, "note": "great"})
    assert ev.args == {"rating": 5, "note": "great"}
    assert ToolInvoked.from_dict(ev.to_dict()) == ev


def test_tool_invoked_to_dict_all_keys() -> None:
    d = ToolInvoked(selector="s", args={"a": 1}).to_dict()
    assert d == {"type": "tool_invoked", "selector": "s", "args": {"a": 1}}


def test_tool_invoked_from_dict_tolerates_missing_args() -> None:
    ev = ToolInvoked.from_dict({"type": "tool_invoked", "selector": "s"})
    assert ev == ToolInvoked(selector="s")
    assert ev.args == {}


def test_tool_invoked_in_registry() -> None:
    assert "tool_invoked" in _REGISTRY
    assert _REGISTRY["tool_invoked"] is ToolInvoked


def test_tool_invoked_event_from_dict() -> None:
    ev = event_from_dict({"type": "tool_invoked", "selector": "panel.search", "args": {"q": 1}})
    assert isinstance(ev, ToolInvoked)
    assert ev.selector == "panel.search"
    assert ev.args == {"q": 1}


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


def test_tool_result_type_discriminator() -> None:
    assert ToolResult.type == "tool_result"
    assert ToolResult(selector="feedback.record").type == "tool_result"


def test_tool_result_defaults() -> None:
    ev = ToolResult(selector="feedback.record")
    assert ev.selector == "feedback.record"
    assert ev.ok is True
    assert ev.result == ""
    assert ev.error == {}


def test_tool_result_is_frozen() -> None:
    ev = ToolResult(selector="feedback.record")
    with pytest.raises(AttributeError):
        ev.ok = False  # type: ignore[misc]


def test_tool_result_round_trip_defaults() -> None:
    ev = ToolResult(selector="feedback.record")
    assert ToolResult.from_dict(ev.to_dict()) == ev


def test_tool_result_round_trip_success_with_result() -> None:
    ev = ToolResult(selector="feedback.record", ok=True, result="42")
    assert ToolResult.from_dict(ev.to_dict()) == ev


def test_tool_result_round_trip_failure_with_error() -> None:
    error = {"code": 3, "message": "boom", "remediation": "try again"}
    ev = ToolResult(selector="feedback.record", ok=False, result="", error=error)
    assert ev.error == error
    assert ToolResult.from_dict(ev.to_dict()) == ev


def test_tool_result_to_dict_all_keys() -> None:
    d = ToolResult(selector="s", ok=False, result="", error={"code": 1}).to_dict()
    assert d == {
        "type": "tool_result",
        "selector": "s",
        "ok": False,
        "result": "",
        "error": {"code": 1},
    }


def test_tool_result_from_dict_tolerates_missing_optional_fields() -> None:
    ev = ToolResult.from_dict({"type": "tool_result", "selector": "s"})
    assert ev == ToolResult(selector="s")
    assert ev.ok is True
    assert ev.result == ""
    assert ev.error == {}


def test_tool_result_in_registry() -> None:
    assert "tool_result" in _REGISTRY
    assert _REGISTRY["tool_result"] is ToolResult


def test_tool_result_event_from_dict() -> None:
    ev = event_from_dict(
        {
            "type": "tool_result",
            "selector": "panel.search",
            "ok": False,
            "error": {"code": 1, "message": "nope", "remediation": "check args"},
        }
    )
    assert isinstance(ev, ToolResult)
    assert ev.ok is False
    assert ev.error == {"code": 1, "message": "nope", "remediation": "check args"}


# ---------------------------------------------------------------------------
# JSONL round-trip for both new events together
# ---------------------------------------------------------------------------


def test_round_trip_tool_events_via_jsonl() -> None:
    evts: list[Event] = [
        ToolInvoked(selector="feedback.record", args={"rating": 5, "note": "great"}),
        ToolResult(selector="feedback.record", ok=True, result="ok"),
        ToolInvoked(selector="panel.search", args={}),
        ToolResult(
            selector="panel.search",
            ok=False,
            result="",
            error={"code": 3, "message": "boom", "remediation": "try again"},
        ),
    ]
    assert loads_events(dumps_events(evts)) == evts


def test_round_trip_tool_invoked_missing_field_raises() -> None:
    text = '{"type": "tool_invoked"}\n'
    with pytest.raises(ValueError, match="selector"):
        loads_events(text)


def test_round_trip_tool_result_missing_field_raises() -> None:
    text = '{"type": "tool_result"}\n'
    with pytest.raises(ValueError, match="selector"):
        loads_events(text)


# ---------------------------------------------------------------------------
# event_from_dict unknown-type error lists the new types
# ---------------------------------------------------------------------------


def test_event_from_dict_unknown_type_lists_new_types() -> None:
    with pytest.raises(ValueError) as exc_info:
        event_from_dict({"type": "bogus"})
    message = str(exc_info.value)
    assert "tool_invoked" in message
    assert "tool_result" in message


# ---------------------------------------------------------------------------
# SelectorAction.args — lock in the existing contract via JSONL round-trip
# ---------------------------------------------------------------------------


def test_selector_action_args_round_trip_via_jsonl() -> None:
    """SelectorAction.args already exists; lock its round-trip through the
    dumps_events/loads_events JSONL helpers (not just to_dict/from_dict)."""
    evts: list[Event] = [
        SelectorAction(selector="panel.search", args={"q": "test", "limit": 10}),
        SelectorAction(selector="panel.search"),
    ]
    result = loads_events(dumps_events(evts))
    assert result == evts
    assert result[0].args == {"q": "test", "limit": 10}
    assert result[1].args == {}


# ---------------------------------------------------------------------------
# Sanity: other pre-existing event types unaffected
# ---------------------------------------------------------------------------


def test_other_event_types_still_round_trip() -> None:
    evts: list[Event] = [
        UserInput(text="hi"),
        KeyPress(key="tab"),
        Tick(delta=2),
        Dismiss(target="popup.x"),
    ]
    assert loads_events(dumps_events(evts)) == evts
