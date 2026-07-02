"""Unit tests for ``agentfront.taui.session.Session`` — the single-process
single-writer live TAUI session (t6, the architectural centerpiece).

Covers the "t6 — Session" spec in the design contract: default construction,
tool dispatch success/failure (with MCP-shape parity against
``agentfront.testing.call_mcp``), the navigation fallback for an unresolved
selector, single-writer atomicity under concurrent human+agent threads
(trail length + replay-equivalence), and ``initial``/``replay_base_index``
semantics for fresh vs. resumed sessions.
"""

from __future__ import annotations

import threading
import time

import pytest

from agentfront import App
from agentfront.errors import AgentfrontError
from agentfront.taui.derive import make_baseline
from agentfront.taui.events import KeyPress, SelectorAction, ToolInvoked, ToolResult
from agentfront.taui.mirror import serialize
from agentfront.taui.reducer import reduce, replay
from agentfront.taui.session import Session
from agentfront.testing import call_mcp

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> App:
    a = App(name="session-test-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    @a.tool
    def boom(message: str) -> None:
        """Always raise a structured AgentfrontError."""
        raise AgentfrontError(code=3, message=message, remediation="fix your input")

    @a.tool
    def explode() -> None:
        """Always raise a generic exception."""
        raise ValueError("kaboom")

    @a.tool
    async def fetch(url: str) -> str:
        """Pretend to fetch a URL (async tool)."""
        return f"fetched {url}"

    @a.tool(group="feedback")
    def record(text: str) -> str:
        """Record feedback."""
        return text

    return a


# ---------------------------------------------------------------------------
# 1. Defaults
# ---------------------------------------------------------------------------


def test_defaults_state_is_baseline(app: App) -> None:
    session = Session(app)
    assert session.state == make_baseline(app)


def test_defaults_mirror_matches_serialize_of_state(app: App) -> None:
    session = Session(app)
    assert session.mirror() == serialize(session.state)


def test_defaults_events_starts_empty(app: App) -> None:
    session = Session(app)
    assert session.events == []


def test_defaults_last_result_is_none(app: App) -> None:
    session = Session(app)
    assert session.last_result is None


def test_defaults_initial_equals_baseline(app: App) -> None:
    session = Session(app)
    assert session.initial == make_baseline(app)


def test_defaults_events_property_is_a_copy(app: App) -> None:
    session = Session(app)
    session.feed_key("down")
    trail = session.events
    trail.append(KeyPress("up"))
    assert len(session.events) == 1  # mutating the returned copy did not affect the session


# ---------------------------------------------------------------------------
# 2. Tool dispatch success — MCP-shape parity with call_mcp
# ---------------------------------------------------------------------------


def test_dispatch_tool_success_executes_and_returns_state(app: App) -> None:
    session = Session(app)
    result_state = session.dispatch(SelectorAction(selector="add", args={"x": 3, "y": 4}))
    assert result_state is session.state


def test_dispatch_tool_success_trail_is_invoked_then_result(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="add", args={"x": 3, "y": 4}))
    assert len(session.events) == 2
    invoked, result = session.events
    assert isinstance(invoked, ToolInvoked)
    assert invoked.selector == "add"
    assert invoked.args == {"x": 3, "y": 4}
    assert isinstance(result, ToolResult)
    assert result.selector == "add"
    assert result.ok is True
    assert result.result == "7"


def test_dispatch_tool_success_conversation_shows_arrow_then_check(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="add", args={"x": 3, "y": 4}))
    lines = [line.text for line in session.state.conversation]
    assert lines == ["→ add", "✓ add: 7"]


def test_dispatch_tool_success_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="add", args={"x": 3, "y": 4}))
    assert session.last_result == call_mcp(app, ["add"], {"x": 3, "y": 4})
    assert session.last_result == {"result": 7}


def test_dispatch_tool_success_grouped_selector_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="feedback.record", args={"text": "hi"}))
    assert session.last_result == call_mcp(app, ["feedback", "record"], {"text": "hi"})
    assert session.last_result == {"result": "hi"}


def test_dispatch_async_tool_resolves_awaitable_and_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="fetch", args={"url": "http://x"}))
    assert session.last_result == call_mcp(app, ["fetch"], {"url": "http://x"})
    assert session.last_result == {"result": "fetched http://x"}


# ---------------------------------------------------------------------------
# 3. Tool dispatch failure — AgentfrontError, generic exception
# ---------------------------------------------------------------------------


def test_dispatch_tool_agentfront_error_last_result_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="boom", args={"message": "bad input"}))
    expected = call_mcp(app, ["boom"], {"message": "bad input"})
    assert session.last_result == expected
    assert expected == {
        "error": {"code": 3, "message": "bad input", "remediation": "fix your input"}
    }


def test_dispatch_tool_agentfront_error_opens_blocking_tool_error_popup(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="boom", args={"message": "bad input"}))
    popup = next(p for p in state.popups if p.id == "popup.tool-error")
    assert popup.visible is True
    assert popup.blocking is True


def test_dispatch_tool_agentfront_error_problems_entry_has_code_message_remediation(
    app: App,
) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="boom", args={"message": "bad input"}))
    assert state.problems[-1] == {
        "selector": "boom",
        "code": 3,
        "message": "bad input",
        "remediation": "fix your input",
    }


def test_dispatch_tool_agentfront_error_trail_result_event_carries_error(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="boom", args={"message": "bad input"}))
    result = session.events[-1]
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error == {"code": 3, "message": "bad input", "remediation": "fix your input"}
    assert result.result == ""


def test_dispatch_tool_generic_exception_matches_call_mcp(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="explode", args={}))
    expected = call_mcp(app, ["explode"], {})
    assert session.last_result == expected
    assert expected == {
        "error": {
            "code": 1,
            "message": "ValueError: kaboom",
            "remediation": "check command arguments",
        }
    }


def test_dispatch_tool_generic_exception_conversation_shows_cross_mark(app: App) -> None:
    session = Session(app)
    state = session.dispatch(SelectorAction(selector="explode", args={}))
    assert state.conversation[-1].text == "✗ explode"


# ---------------------------------------------------------------------------
# 4. Unknown selector — pure navigation fallback
# ---------------------------------------------------------------------------


def test_dispatch_unresolved_selector_folds_pure_navigation(app: App) -> None:
    session = Session(app)
    session.feed_key("down")  # move focus away from the default first
    prior_state = session.state
    action = SelectorAction(selector="input.prompt", args={})

    result_state = session.dispatch(action)

    assert result_state == reduce(prior_state, action)


def test_dispatch_unresolved_selector_last_result_unchanged(app: App) -> None:
    session = Session(app)
    action = SelectorAction(selector="input.prompt", args={})
    session.dispatch(action)
    assert session.last_result is None


def test_dispatch_unresolved_selector_trail_gains_exactly_the_action(app: App) -> None:
    session = Session(app)
    action = SelectorAction(selector="input.prompt", args={})
    session.dispatch(action)
    assert session.events == [action]


def test_dispatch_completely_unknown_selector_is_a_no_op_navigation(app: App) -> None:
    session = Session(app)
    prior_state = session.state
    action = SelectorAction(selector="totally.unknown.path", args={})
    result_state = session.dispatch(action)
    assert result_state == reduce(prior_state, action)
    assert result_state == prior_state  # not in focus_order -> _reduce_selector no-ops
    assert session.events == [action]
    assert session.last_result is None


def test_dispatch_after_tool_last_result_stays_set_through_navigation(app: App) -> None:
    session = Session(app)
    session.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 1}))
    first_result = session.last_result
    session.dispatch(SelectorAction(selector="input.prompt", args={}))
    assert session.last_result == first_result


# ---------------------------------------------------------------------------
# 5. Single-writer under threads — no lost/torn appends, trail is truth
# ---------------------------------------------------------------------------


def test_single_writer_concurrent_feed_key_and_dispatch_no_lost_or_torn_events(app: App) -> None:
    a = App(name="race-app", version="0.1.0")

    @a.tool
    def slow_ok(n: int) -> int:
        time.sleep(0.002)
        return n * 2

    session = Session(a)

    num_keys = 60
    actions: list[SelectorAction] = []
    tool_calls = 0
    nav_calls = 0
    for i in range(30):
        if i % 2 == 0:
            actions.append(SelectorAction(selector="slow_ok", args={"n": i}))
            tool_calls += 1
        else:
            actions.append(SelectorAction(selector="input.prompt", args={}))
            nav_calls += 1

    def feed_keys() -> None:
        for i in range(num_keys):
            session.feed_key("down" if i % 2 == 0 else "up")

    def dispatch_actions() -> None:
        for action in actions:
            session.dispatch(action)

    t1 = threading.Thread(target=feed_keys)
    t2 = threading.Thread(target=dispatch_actions)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    expected_len = num_keys + 2 * tool_calls + nav_calls
    assert len(session.events) == expected_len
    assert replay(session.events, initial=session.initial) == session.state


def test_single_writer_concurrent_dispatch_only_no_lost_or_torn_events() -> None:
    """Two threads BOTH dispatching (mix of tool + navigation) concurrently."""
    a = App(name="race-app-2", version="0.1.0")

    @a.tool
    def slow_ok(n: int) -> int:
        time.sleep(0.002)
        return n

    @a.tool
    def slow_boom() -> None:
        time.sleep(0.002)
        raise ValueError("boom")

    session = Session(a)

    def make_actions(offset: int) -> list[SelectorAction]:
        actions: list[SelectorAction] = []
        for i in range(15):
            n = offset + i
            if n % 3 == 0:
                actions.append(SelectorAction(selector="slow_boom", args={}))
            elif n % 3 == 1:
                actions.append(SelectorAction(selector="slow_ok", args={"n": n}))
            else:
                actions.append(SelectorAction(selector="input.prompt", args={}))
        return actions

    worker_actions = [make_actions(0), make_actions(100)]

    def worker(actions: list[SelectorAction]) -> None:
        for action in actions:
            session.dispatch(action)

    threads = [threading.Thread(target=worker, args=(actions,)) for actions in worker_actions]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Expected length is derived from the exact actions generated above (not
    # re-guessed), so the assertion holds regardless of thread interleaving:
    # a tool dispatch folds 2 events (invoked+result); a navigation fallback
    # (selector == "input.prompt", unresolved against this app's registry)
    # folds exactly 1.
    all_actions = worker_actions[0] + worker_actions[1]
    tool_dispatches = sum(1 for a in all_actions if a.selector != "input.prompt")
    nav_dispatches = sum(1 for a in all_actions if a.selector == "input.prompt")
    expected_len = tool_dispatches * 2 + nav_dispatches

    events = session.events
    assert len(events) == expected_len
    assert replay(events, initial=session.initial) == session.state


# ---------------------------------------------------------------------------
# 6. initial / replay_base_index — fresh vs. resumed sessions
# ---------------------------------------------------------------------------


def test_fresh_session_replay_base_index_is_zero(app: App) -> None:
    session = Session(app)
    assert session.replay_base_index == 0


def test_fresh_session_full_trail_replays_from_initial(app: App) -> None:
    session = Session(app)
    session.feed_key("down")
    session.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    session.feed_key("up")

    assert replay(session.events, initial=session.initial) == session.state
    # For a fresh session replay_base_index == 0, so this is equivalent.
    assert replay(session.events[session.replay_base_index :], initial=session.initial) == (
        session.state
    )


def test_resumed_session_initial_is_the_state_argument_not_replayed_trail(app: App) -> None:
    origin = Session(app)
    origin.feed_key("down")
    origin.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    prior_events = origin.events
    prior_state = origin.state

    resumed = Session(app, state=prior_state, events=prior_events)

    assert resumed.initial == prior_state
    assert resumed.initial is not make_baseline(app)
    assert resumed.state == prior_state
    assert resumed.events == prior_events


def test_resumed_session_replay_base_index_equals_prior_trail_length(app: App) -> None:
    origin = Session(app)
    origin.feed_key("down")
    origin.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    prior_events = origin.events

    resumed = Session(app, state=origin.state, events=prior_events)

    assert resumed.replay_base_index == len(prior_events) == 3


def test_resumed_session_new_events_replay_on_top_of_initial(app: App) -> None:
    origin = Session(app)
    origin.feed_key("down")
    origin.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    prior_events = origin.events
    prior_state = origin.state

    resumed = Session(app, state=prior_state, events=prior_events)
    resumed.feed_key("up")
    resumed.dispatch(SelectorAction(selector="feedback.record", args={"text": "hi"}))

    new_events = resumed.events[resumed.replay_base_index :]
    assert replay(new_events, initial=resumed.initial) == resumed.state

    # And the prior events are untouched bookkeeping, not replayed underneath.
    assert resumed.events[: resumed.replay_base_index] == prior_events


def test_resumed_session_from_a_snapshot_style_empty_prior_trail(app: App) -> None:
    """events=[] with a non-baseline state (a hand-built resume point)."""
    custom_state = reduce(make_baseline(app), KeyPress("down"))
    resumed = Session(app, state=custom_state, events=[])

    assert resumed.initial == custom_state
    assert resumed.replay_base_index == 0
    assert resumed.state == custom_state
    assert replay(resumed.events, initial=resumed.initial) == resumed.state
