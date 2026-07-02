"""Tests for ``agentfront.testing.taui`` — the public TAUI testing helpers (t11).

Covers the "t11 — testing TAUI helpers" spec in the design contract:
``drive`` (fold a scripted event list, executing tools for ``SelectorAction``
events via ``Session.dispatch``), ``assert_agent_human_parity`` (agent
selector-dispatch vs. human down-key navigation reach the same state),
``assert_replay_equivalent`` (a session's trail replays to its own state),
and the LAZY ``resume`` re-export (PEP 562 ``__getattr__``) that tolerates
``agentfront.taui.snapshot.resume`` not existing yet in this worktree — a
sibling task (t10) adds it in parallel.
"""

from __future__ import annotations

import pytest

import agentfront.taui.snapshot as taui_snapshot
import agentfront.testing as testing_pkg
import agentfront.testing.taui as testing_taui
from agentfront import App
from agentfront.taui.derive import make_baseline
from agentfront.taui.events import KeyPress, SelectorAction, ToolInvoked, ToolResult, UserInput
from agentfront.taui.reducer import focus_order
from agentfront.taui.session import Session
from agentfront.testing.taui import (
    Snapshot,
    assert_agent_human_parity,
    assert_replay_equivalent,
    drive,
    read_snapshot,
    replay,
    write_snapshot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> App:
    a = App(name="testing-taui-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    @a.tool(group="feedback")
    def record(text: str) -> str:
        """Record feedback."""
        return text

    return a


@pytest.fixture
def parity_app() -> App:
    """An app whose baseline has 2+ panel items that are NOT registered tools.

    Host commands (``cmd.<name>`` panel items) never resolve via
    ``App.get_by_path`` (that only searches the tool registry), so dispatching
    one of these selectors is guaranteed to be pure navigation — exactly what
    ``assert_agent_human_parity`` needs to compare agent vs. human trails.
    """
    a = App(name="parity-app", version="0.1.0")

    def handle_aaa(**kwargs: object) -> str:
        return "aaa"

    def handle_bbb(**kwargs: object) -> str:
        return "bbb"

    a.add_command("aaa", handle_aaa, help="AAA command")
    a.add_command("bbb", handle_bbb, help="BBB command")
    return a


# ---------------------------------------------------------------------------
# 1. drive()
# ---------------------------------------------------------------------------


def test_drive_returns_a_session(app: App) -> None:
    session = drive(app, [])
    assert isinstance(session, Session)
    assert session.state == make_baseline(app)


def test_drive_executes_tool_selector_actions_and_folds_the_rest(app: App) -> None:
    events = [
        UserInput(text="hello"),
        SelectorAction(selector="add", args={"x": 3, "y": 4}),
        KeyPress(key="down"),
    ]

    session = drive(app, events)

    lines = [line.text for line in session.state.conversation]
    assert "hello" in lines
    assert "→ add" in lines
    assert "✓ add: 7" in lines


def test_drive_trail_shape_expands_selector_action_to_invoked_and_result(app: App) -> None:
    events = [
        UserInput(text="hello"),
        SelectorAction(selector="add", args={"x": 3, "y": 4}),
        KeyPress(key="down"),
    ]

    session = drive(app, events)
    trail = session.events

    assert len(trail) == 4
    assert isinstance(trail[0], UserInput)
    assert trail[0].text == "hello"
    assert isinstance(trail[1], ToolInvoked)
    assert trail[1].selector == "add"
    assert trail[1].args == {"x": 3, "y": 4}
    assert isinstance(trail[2], ToolResult)
    assert trail[2].selector == "add"
    assert trail[2].ok is True
    assert trail[2].result == "7"
    assert isinstance(trail[3], KeyPress)
    assert trail[3].key == "down"


def test_drive_non_tool_selector_action_folds_as_pure_navigation(app: App) -> None:
    events = [SelectorAction(selector="input.prompt", args={})]

    session = drive(app, events)

    assert session.events == events
    assert session.state.focused == "input.prompt"
    assert session.last_result is None


# ---------------------------------------------------------------------------
# 2. assert_agent_human_parity
# ---------------------------------------------------------------------------


def test_assert_agent_human_parity_passes_for_reachable_panel_item(parity_app: App) -> None:
    order = focus_order(make_baseline(parity_app))
    assert len(order) >= 3  # cmd.aaa, cmd.bbb, input.prompt
    selector = order[1]
    assert selector == "cmd.bbb"

    assert_agent_human_parity(parity_app, selector)  # must not raise


def test_assert_agent_human_parity_raises_for_unreachable_selector(parity_app: App) -> None:
    with pytest.raises(AssertionError):
        assert_agent_human_parity(parity_app, "no.such.selector")


# ---------------------------------------------------------------------------
# 3. assert_replay_equivalent
# ---------------------------------------------------------------------------


def test_assert_replay_equivalent_passes_on_fresh_session(app: App) -> None:
    session = Session(app)
    session.feed_key("down")
    session.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    session.feed_key("up")

    assert_replay_equivalent(session)  # must not raise


def test_assert_replay_equivalent_passes_on_resumed_session(app: App) -> None:
    origin = Session(app)
    origin.feed_key("down")
    origin.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 2}))
    prior_events = origin.events
    prior_state = origin.state

    resumed = Session(app, state=prior_state, events=prior_events)
    resumed.feed_key("up")
    resumed.dispatch(SelectorAction(selector="feedback.record", args={"text": "hi"}))

    assert_replay_equivalent(resumed)  # must not raise


def test_assert_replay_equivalent_raises_on_mismatch(app: App) -> None:
    session = Session(app)
    session.feed_key("down")
    # Mutate the session's live state object in place (bypassing the frozen
    # dataclass guard) so it no longer matches what replaying its own trail
    # from its own initial state would produce.
    object.__setattr__(session.state, "focused", "corrupted-by-test")

    with pytest.raises(AssertionError):
        assert_replay_equivalent(session)


# ---------------------------------------------------------------------------
# 4. Re-exports (eager) + lazy resume (PEP 562)
# ---------------------------------------------------------------------------


def test_eager_reexports_are_the_same_objects_as_their_source() -> None:
    from agentfront.taui.reducer import replay as reducer_replay
    from agentfront.taui.snapshot import Snapshot as snapshot_Snapshot
    from agentfront.taui.snapshot import read_snapshot as snapshot_read_snapshot
    from agentfront.taui.snapshot import write_snapshot as snapshot_write_snapshot

    assert write_snapshot is snapshot_write_snapshot
    assert read_snapshot is snapshot_read_snapshot
    assert Snapshot is snapshot_Snapshot
    assert replay is reducer_replay


def test_lazy_resume_reexport_behavior_matches_sibling_availability() -> None:
    """resume is importable once agentfront.taui.snapshot grows it (t10, in
    parallel); until then, accessing it raises a clear AttributeError."""
    if hasattr(taui_snapshot, "resume"):
        assert testing_taui.resume is taui_snapshot.resume
        assert testing_pkg.resume is taui_snapshot.resume
    else:
        with pytest.raises(AttributeError, match="resume"):
            _ = testing_taui.resume
        with pytest.raises(AttributeError, match="resume"):
            _ = testing_pkg.resume


def test_unknown_attribute_still_raises_attribute_error() -> None:
    with pytest.raises(AttributeError):
        _ = testing_taui.definitely_not_a_real_attribute


# ---------------------------------------------------------------------------
# 5. Package-level exports (__init__.py)
# ---------------------------------------------------------------------------


def test_package_reexports_drive_and_assertions() -> None:
    assert testing_pkg.drive is drive
    assert testing_pkg.assert_agent_human_parity is assert_agent_human_parity
    assert testing_pkg.assert_replay_equivalent is assert_replay_equivalent
    assert testing_pkg.write_snapshot is write_snapshot
    assert testing_pkg.read_snapshot is read_snapshot
    assert testing_pkg.Snapshot is Snapshot
    assert testing_pkg.replay is replay
