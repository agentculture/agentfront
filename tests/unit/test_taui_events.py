"""Unit tests for agentfront.taui.events — event union + JSONL helpers."""

from __future__ import annotations

import pytest

from agentfront.taui.events import (
    _REGISTRY,
    Dismiss,
    Event,
    KeyPress,
    SelectorAction,
    SkillSuggested,
    Tick,
    UserInput,
    WorkStep,
    dumps_events,
    event_from_dict,
    loads_events,
)

# ---------------------------------------------------------------------------
# Round-trip via to_dict / from_dict
# ---------------------------------------------------------------------------


def test_user_input_round_trip() -> None:
    ev = UserInput(text="hello")
    assert ev.type == "user_input"
    assert UserInput.from_dict(ev.to_dict()) == ev


def test_key_press_round_trip() -> None:
    ev = KeyPress(key="enter")
    assert ev.type == "key"
    assert KeyPress.from_dict(ev.to_dict()) == ev


def test_selector_action_round_trip() -> None:
    ev = SelectorAction(selector="panel.search", args={"q": "test"})
    assert ev.type == "selector_action"
    assert SelectorAction.from_dict(ev.to_dict()) == ev


def test_selector_action_defaults() -> None:
    ev = SelectorAction(selector="panel.search")
    assert ev.args == {}
    assert SelectorAction.from_dict(ev.to_dict()) == ev


def test_tick_round_trip() -> None:
    ev = Tick(delta=1)
    assert ev.type == "tick"
    assert Tick.from_dict(ev.to_dict()) == ev


def test_tick_custom_delta() -> None:
    ev = Tick(delta=5)
    assert ev.type == "tick"
    assert Tick.from_dict(ev.to_dict()) == ev


def test_dismiss_round_trip() -> None:
    ev = Dismiss(target="popup.confirm")
    assert ev.type == "dismiss"
    assert Dismiss.from_dict(ev.to_dict()) == ev


def test_dismiss_defaults() -> None:
    ev = Dismiss()
    assert ev.target == ""
    assert Dismiss.from_dict(ev.to_dict()) == ev


# ---------------------------------------------------------------------------
# event_from_dict dispatch
# ---------------------------------------------------------------------------


def test_event_from_dict_dispatches() -> None:
    assert event_from_dict({"type": "user_input", "text": "hi"}) == UserInput(text="hi")
    assert event_from_dict({"type": "key", "key": "tab"}) == KeyPress(key="tab")
    assert event_from_dict({"type": "selector_action", "selector": "s"}) == SelectorAction(
        selector="s"
    )
    assert event_from_dict({"type": "tick"}) == Tick()
    assert event_from_dict({"type": "dismiss"}) == Dismiss()


def test_event_from_dict_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown"):
        event_from_dict({"type": "bogus"})


def test_event_from_dict_not_a_dict() -> None:
    with pytest.raises(ValueError, match="dict"):
        event_from_dict("not a dict")  # type: ignore[arg-type]


def test_event_from_dict_missing_type() -> None:
    with pytest.raises(ValueError, match="type"):
        event_from_dict({})


def test_event_from_dict_missing_required_field() -> None:
    with pytest.raises(ValueError, match="text"):
        event_from_dict({"type": "user_input"})


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------


def test_dumps_events_empty() -> None:
    assert dumps_events([]) == ""


def test_dumps_events_single() -> None:
    result = dumps_events([UserInput(text="hi")])
    assert result == '{"type": "user_input", "text": "hi"}\n'


def test_dumps_events_multiple() -> None:
    evts: list[Event] = [
        UserInput(text="hello"),
        KeyPress(key="enter"),
        SelectorAction(selector="s", args={"a": 1}),
        Tick(delta=2),
        Dismiss(target="p"),
    ]
    lines = dumps_events(evts).splitlines()
    assert len(lines) == 5


def test_loads_events_empty() -> None:
    assert loads_events("") == []


def test_loads_events_single() -> None:
    result = loads_events('{"type": "key", "key": "esc"}\n')
    assert result == [KeyPress(key="esc")]


def test_loads_events_skips_blank_lines() -> None:
    text = '{"type": "tick"}\n\n{"type": "dismiss"}\n'
    result = loads_events(text)
    assert result == [Tick(), Dismiss()]


def test_round_trip_all_event_types() -> None:
    """loads_events(dumps_events(evs)) round-trips every event type."""
    evts: list[Event] = [
        UserInput(text="hello"),
        KeyPress(key="tab"),
        SelectorAction(selector="panel.search", args={"q": "test"}),
        Tick(delta=3),
        Dismiss(target="popup.confirm"),
    ]
    assert loads_events(dumps_events(evts)) == evts


def test_round_trip_unknown_type_raises() -> None:
    """An unknown type in JSONL raises ValueError during loads."""
    text = '{"type": "unknown_event"}\n'
    with pytest.raises(ValueError, match="unknown"):
        loads_events(text)


def test_round_trip_missing_field_raises() -> None:
    """A missing required field raises ValueError during loads."""
    text = '{"type": "user_input"}\n'
    with pytest.raises(ValueError, match="text"):
        loads_events(text)


# ---------------------------------------------------------------------------
# SkillSuggested
# ---------------------------------------------------------------------------


def test_skill_suggested_defaults() -> None:
    """SkillSuggested has sensible defaults for all fields."""
    ev = SkillSuggested()
    assert ev.type == "skill_suggested"
    assert ev.skill == ""
    assert ev.reason == ""
    assert ev.semantic == "stronger_agent_recommended"
    assert ev.theme == "skill_suggested"


def test_skill_suggested_round_trip() -> None:
    """SkillSuggested round-trips via to_dict / from_dict."""
    ev = SkillSuggested(skill="search", reason="better coverage", semantic="custom", theme="t")
    assert SkillSuggested.from_dict(ev.to_dict()) == ev


def test_skill_suggested_round_trip_defaults() -> None:
    """SkillSuggested() with defaults round-trips cleanly."""
    ev = SkillSuggested()
    assert SkillSuggested.from_dict(ev.to_dict()) == ev


def test_skill_suggested_to_dict_contains_type() -> None:
    """to_dict emits the 'type' key."""
    d = SkillSuggested().to_dict()
    assert d["type"] == "skill_suggested"


def test_skill_suggested_to_dict_all_keys() -> None:
    """to_dict emits type, skill, reason, semantic, theme."""
    d = SkillSuggested(skill="s", reason="r").to_dict()
    assert set(d.keys()) == {"type", "skill", "reason", "semantic", "theme"}


def test_skill_suggested_event_from_dict() -> None:
    """event_from_dict reconstructs a SkillSuggested from a type-keyed dict."""
    ev = event_from_dict({"type": "skill_suggested", "skill": "search", "reason": "faster"})
    assert isinstance(ev, SkillSuggested)
    assert ev.skill == "search"
    assert ev.reason == "faster"


def test_skill_suggested_event_from_dict_defaults() -> None:
    """event_from_dict with only 'type' uses .get defaults."""
    ev = event_from_dict({"type": "skill_suggested"})
    assert isinstance(ev, SkillSuggested)
    assert ev == SkillSuggested()


def test_skill_suggested_in_registry() -> None:
    """'skill_suggested' is registered in _REGISTRY."""
    assert "skill_suggested" in _REGISTRY
    assert _REGISTRY["skill_suggested"] is SkillSuggested


# ---------------------------------------------------------------------------
# WorkStep
# ---------------------------------------------------------------------------


def test_work_step_defaults() -> None:
    """WorkStep has sensible defaults for all fields."""
    ev = WorkStep()
    assert ev.type == "work_step"
    assert ev.label == ""
    assert ev.ok is True
    assert ev.error == ""


def test_work_step_round_trip() -> None:
    """WorkStep round-trips via to_dict / from_dict."""
    ev = WorkStep(label="fetching data", ok=False, error="timeout")
    assert WorkStep.from_dict(ev.to_dict()) == ev


def test_work_step_round_trip_defaults() -> None:
    """WorkStep() with defaults round-trips cleanly."""
    ev = WorkStep()
    assert WorkStep.from_dict(ev.to_dict()) == ev


def test_work_step_to_dict_contains_type() -> None:
    """to_dict emits the 'type' key."""
    d = WorkStep().to_dict()
    assert d["type"] == "work_step"


def test_work_step_to_dict_all_keys() -> None:
    """to_dict emits type, label, ok, error."""
    d = WorkStep(label="l", ok=False, error="e").to_dict()
    assert set(d.keys()) == {"type", "label", "ok", "error"}


def test_work_step_event_from_dict() -> None:
    """event_from_dict reconstructs a WorkStep from a type-keyed dict."""
    ev = event_from_dict(
        {"type": "work_step", "label": "writing", "ok": False, "error": "disk full"}
    )
    assert isinstance(ev, WorkStep)
    assert ev.label == "writing"
    assert ev.ok is False
    assert ev.error == "disk full"


def test_work_step_event_from_dict_defaults() -> None:
    """event_from_dict with only 'type' uses .get defaults."""
    ev = event_from_dict({"type": "work_step"})
    assert isinstance(ev, WorkStep)
    assert ev == WorkStep()


def test_work_step_in_registry() -> None:
    """'work_step' is registered in _REGISTRY."""
    assert "work_step" in _REGISTRY
    assert _REGISTRY["work_step"] is WorkStep


# ---------------------------------------------------------------------------
# JSONL round-trip including new event types
# ---------------------------------------------------------------------------


def test_round_trip_all_event_types_including_new() -> None:
    """loads_events(dumps_events(evs)) round-trips SkillSuggested and WorkStep too."""
    evts: list[Event] = [
        SkillSuggested(skill="search", reason="faster"),
        WorkStep(label="step 1", ok=True),
        WorkStep(label="step 2", ok=False, error="net error"),
    ]
    assert loads_events(dumps_events(evts)) == evts
