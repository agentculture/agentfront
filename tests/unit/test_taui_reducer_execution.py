"""Unit tests for the reducer's execution folds — ToolInvoked / ToolResult.

Covers the "Reducer folds (t5)" spec in the design contract: conversation
lines, work_item start/advance/stop transitions, the blocking
popup.tool-error popup on failure, the problems entry it appends, dismiss
semantics, malformed-payload resilience (never raises), and deterministic
replay of a trail containing the new events.
"""

from __future__ import annotations

from agentfront.taui.events import Dismiss, KeyPress, ToolInvoked, ToolResult
from agentfront.taui.reducer import reduce, replay
from agentfront.taui.selectors import resolve
from agentfront.taui.state import TAUIState, WorkItem

# ---------------------------------------------------------------------------
# ToolInvoked — conversation + work_item start/advance
# ---------------------------------------------------------------------------


def test_tool_invoked_appends_conversation_arrow_line() -> None:
    state = TAUIState()
    result = reduce(state, ToolInvoked(selector="feedback.record"))
    assert len(result.conversation) == 1
    assert result.conversation[0].text == "→ feedback.record"


def test_tool_invoked_starts_work_item_when_none() -> None:
    state = TAUIState(work_item=None)
    result = reduce(state, ToolInvoked(selector="feedback.record"))
    assert result.work_item is not None
    assert result.work_item.task_id == "feedback.record"
    assert result.work_item.running is True
    assert result.work_item.step_count == 0


def test_tool_invoked_advances_existing_work_item() -> None:
    state = TAUIState(work_item=WorkItem(task_id="other", step_count=2, running=False))
    result = reduce(state, ToolInvoked(selector="feedback.record"))
    assert result.work_item is not None
    # task_id of an existing work item is preserved (advance, not replace).
    assert result.work_item.task_id == "other"
    assert result.work_item.step_count == 3
    assert result.work_item.running is True


def test_tool_invoked_pure_input_unchanged() -> None:
    state = TAUIState(work_item=WorkItem(task_id="t1"))
    original = state.to_dict()
    reduce(state, ToolInvoked(selector="feedback.record"))
    assert state.to_dict() == original


# ---------------------------------------------------------------------------
# ToolResult(ok=True) — success path
# ---------------------------------------------------------------------------


def test_tool_result_success_appends_check_line_without_result() -> None:
    state = TAUIState()
    result = reduce(state, ToolResult(selector="feedback.record", ok=True, result=""))
    assert len(result.conversation) == 1
    assert result.conversation[0].text == "✓ feedback.record"


def test_tool_result_success_appends_check_line_with_result() -> None:
    state = TAUIState()
    result = reduce(state, ToolResult(selector="feedback.record", ok=True, result="42"))
    assert result.conversation[0].text == "✓ feedback.record: 42"


def test_tool_result_success_sets_work_item_running_false() -> None:
    state = TAUIState(work_item=WorkItem(task_id="feedback.record", running=True))
    result = reduce(state, ToolResult(selector="feedback.record", ok=True))
    assert result.work_item is not None
    assert result.work_item.running is False


def test_tool_result_success_without_work_item_stays_none() -> None:
    state = TAUIState(work_item=None)
    result = reduce(state, ToolResult(selector="feedback.record", ok=True))
    assert result.work_item is None


def test_tool_result_success_does_not_open_popup() -> None:
    state = TAUIState()
    result = reduce(state, ToolResult(selector="feedback.record", ok=True))
    assert result.popups == []


def test_tool_result_success_pure_input_unchanged() -> None:
    state = TAUIState(work_item=WorkItem(task_id="t1", running=True))
    original = state.to_dict()
    reduce(state, ToolResult(selector="feedback.record", ok=True, result="v"))
    assert state.to_dict() == original


# ---------------------------------------------------------------------------
# ToolResult(ok=False) — failure path
# ---------------------------------------------------------------------------


def test_tool_result_failure_opens_visible_blocking_popup() -> None:
    state = TAUIState()
    error = {"code": 3, "message": "boom", "remediation": "try again"}
    result = reduce(state, ToolResult(selector="feedback.record", ok=False, error=error))
    tool_error = [p for p in result.popups if p.id == "popup.tool-error"]
    assert len(tool_error) == 1
    popup = tool_error[0]
    assert popup.kind == "error"
    assert popup.visible is True
    assert popup.blocking is True
    assert popup.opened_by == "system"
    assert popup.reason == "tool_failed"
    assert popup.message == "boom"


def test_tool_result_failure_popup_action_is_esc_dismiss() -> None:
    state = TAUIState()
    result = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    popup = next(p for p in result.popups if p.id == "popup.tool-error")
    assert len(popup.actions) == 1
    action = popup.actions[0]
    assert action.selector == "popup.tool-error.dismiss"
    assert action.input == "esc"
    assert action.description == "Dismiss"
    # The dismiss action selector must resolve inside the resulting state.
    assert resolve(result, action.selector) is action


def test_tool_result_failure_default_message_when_no_message_key() -> None:
    state = TAUIState()
    result = reduce(state, ToolResult(selector="feedback.record", ok=False, error={}))
    popup = next(p for p in result.popups if p.id == "popup.tool-error")
    assert popup.message == "Tool failed"


def test_tool_result_failure_appends_problems_entry_with_selector_and_error() -> None:
    state = TAUIState()
    error = {"code": 3, "message": "boom", "remediation": "try again"}
    result = reduce(state, ToolResult(selector="feedback.record", ok=False, error=error))
    assert len(result.problems) == 1
    assert result.problems[0] == {
        "selector": "feedback.record",
        "code": 3,
        "message": "boom",
        "remediation": "try again",
    }


def test_tool_result_failure_appends_cross_mark_conversation_line() -> None:
    state = TAUIState()
    result = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    assert result.conversation[-1].text == "✗ feedback.record"


def test_tool_result_failure_sets_work_item_running_false() -> None:
    state = TAUIState(work_item=WorkItem(task_id="feedback.record", running=True))
    result = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    assert result.work_item is not None
    assert result.work_item.running is False


def test_tool_result_failure_without_work_item_stays_none() -> None:
    state = TAUIState(work_item=None)
    result = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    assert result.work_item is None


def test_tool_result_repeated_failure_refreshes_single_popup() -> None:
    """Two failing ToolResults keep ONE popup.tool-error (upsert, not append)."""
    state = TAUIState()
    s1 = reduce(state, ToolResult(selector="a", ok=False, error={"message": "first"}))
    s2 = reduce(s1, ToolResult(selector="b", ok=False, error={"message": "second"}))
    tool_errors = [p for p in s2.popups if p.id == "popup.tool-error"]
    assert len(tool_errors) == 1
    assert tool_errors[0].message == "second"
    assert len(s2.problems) == 2  # both failures still recorded in problems


def test_tool_result_failure_pure_input_unchanged() -> None:
    state = TAUIState(work_item=WorkItem(task_id="t1", running=True))
    original = state.to_dict()
    reduce(state, ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}))
    assert state.to_dict() == original


# ---------------------------------------------------------------------------
# Dismissing popup.tool-error clears visible AND blocking
# ---------------------------------------------------------------------------


def test_dismiss_tool_error_clears_visible_and_blocking() -> None:
    state = TAUIState()
    failed = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    popup = next(p for p in failed.popups if p.id == "popup.tool-error")
    assert popup.visible is True
    assert popup.blocking is True

    dismissed = reduce(failed, Dismiss(target="popup.tool-error"))
    popup2 = next(p for p in dismissed.popups if p.id == "popup.tool-error")
    assert popup2.visible is False
    assert popup2.blocking is False


def test_keypress_esc_dismisses_topmost_tool_error_popup() -> None:
    state = TAUIState()
    failed = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    dismissed = reduce(failed, KeyPress("esc"))
    popup = next(p for p in dismissed.popups if p.id == "popup.tool-error")
    assert popup.visible is False
    assert popup.blocking is False


def test_dismiss_tool_error_keeps_layout_and_lifecycle_diagnosis_ok() -> None:
    from agentfront.taui.diagnose import diagnose_structured

    state = TAUIState()
    failed = reduce(
        state,
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
    )
    assert diagnose_structured(failed).ok is True
    dismissed = reduce(failed, Dismiss(target="popup.tool-error"))
    assert diagnose_structured(dismissed).ok is True


# ---------------------------------------------------------------------------
# Malformed payloads never raise (degrade like _reduce_tick)
# ---------------------------------------------------------------------------


def test_tool_result_non_dict_error_degrades_gracefully() -> None:
    state = TAUIState()
    bad = ToolResult(selector="x", ok=False, error=None)  # type: ignore[arg-type]
    result = reduce(state, bad)
    assert isinstance(result, TAUIState)
    popup = next(p for p in result.popups if p.id == "popup.tool-error")
    assert popup.message == "Tool failed"
    assert result.problems[-1] == {"selector": "x"}


def test_tool_result_error_missing_keys_degrades_gracefully() -> None:
    state = TAUIState()
    bad = ToolResult(selector="x", ok=False, error={"unexpected": "shape"})
    result = reduce(state, bad)
    popup = next(p for p in result.popups if p.id == "popup.tool-error")
    assert popup.message == "Tool failed"
    assert result.problems[-1] == {"selector": "x", "unexpected": "shape"}


def test_tool_result_error_non_string_message_degrades_gracefully() -> None:
    """A non-string message (e.g. from a hand-edited trail) must not crash the
    popup message fold — falsy values fall back to the default message."""
    state = TAUIState()
    bad = ToolResult(selector="x", ok=False, error={"message": None})
    result = reduce(state, bad)
    popup = next(p for p in result.popups if p.id == "popup.tool-error")
    assert popup.message == "Tool failed"


# ---------------------------------------------------------------------------
# Replay determinism over a trail containing the new events
# ---------------------------------------------------------------------------


def test_replay_execution_trail_matches_manual_reduction() -> None:
    events = [
        ToolInvoked(selector="feedback.record", args={"rating": 5}),
        ToolResult(selector="feedback.record", ok=True, result="ok"),
        ToolInvoked(selector="panel.search"),
        ToolResult(
            selector="panel.search",
            ok=False,
            error={"code": 1, "message": "nope", "remediation": "check args"},
        ),
    ]
    s = TAUIState()
    for ev in events:
        s = reduce(s, ev)
    replayed = replay(events, TAUIState())
    assert replayed.to_dict() == s.to_dict()


def test_replay_execution_trail_is_deterministic_across_runs() -> None:
    events = [
        ToolInvoked(selector="feedback.record"),
        ToolResult(selector="feedback.record", ok=True, result="42"),
        ToolInvoked(selector="panel.search"),
        ToolResult(selector="panel.search", ok=False, error={"message": "boom"}),
        Dismiss(target="popup.tool-error"),
    ]
    r1 = replay(events)
    r2 = replay(events)
    assert r1.to_dict() == r2.to_dict()


def test_replay_execution_trail_work_item_final_state() -> None:
    """A start -> fail -> retry -> succeed trail ends with running=False and the
    step_count reflecting each ToolInvoked."""
    events = [
        ToolInvoked(selector="feedback.record"),
        ToolResult(selector="feedback.record", ok=False, error={"message": "boom"}),
        ToolInvoked(selector="feedback.record"),
        ToolResult(selector="feedback.record", ok=True, result="done"),
    ]
    result = replay(events)
    assert result.work_item is not None
    assert result.work_item.task_id == "feedback.record"
    assert result.work_item.running is False
    assert result.work_item.step_count == 1  # advanced once (second ToolInvoked)
    assert len(result.problems) == 1
    assert result.conversation[-1].text == "✓ feedback.record: done"


# ---------------------------------------------------------------------------
# reduce() never raises on ToolInvoked/ToolResult
# ---------------------------------------------------------------------------


def test_reduce_never_raises_on_tool_events() -> None:
    state = TAUIState()
    payloads = [
        ToolInvoked(selector=""),
        ToolResult(selector="", ok=True, result=""),
        ToolResult(selector="", ok=False, error={}),
        ToolResult(selector="x", ok=False, error=None),  # type: ignore[arg-type]
    ]
    s = state
    for ev in payloads:
        s = reduce(s, ev)
    assert isinstance(s, TAUIState)
