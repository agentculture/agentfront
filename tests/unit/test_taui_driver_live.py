"""Unit tests for ``agentfront.taui.driver.LiveDriver`` (t9).

LiveDriver is the human+agent front end over a single live
``agentfront.taui.session.Session``: the human side folds keys (and popup
button presses) via ``feed_key``, the agent side dispatches selectors
directly via ``dispatch``, and both routes write through the SAME session so
either audience's action is visible in the other's next repaint.

Covers the design contract's t9 acceptance list:
1. Popup buttons ACT (regression: not inert) — a ``.dismiss`` action hides
   and unblocks its popup; a non-dismiss action dispatches its selector
   through the session.
2. No quit-trap — "q" always sets ``running = False``, even with a blocking
   popup visible, and ``run`` stops early once that happens.
3. Agent dispatch is visible in the next render.
4. Plain keys route through ``session.feed_key`` unchanged.
5. Both sides share ONE session — interleaved agent/human actions preserve
   call order in ``session.events`` and stay replay-equivalent.
"""

from __future__ import annotations

import pytest

from agentfront import App
from agentfront.taui.driver import LiveDriver
from agentfront.taui.events import KeyPress, SelectorAction
from agentfront.taui.reducer import reduce, replay
from agentfront.taui.session import Session
from agentfront.taui.state import Action, Panel, PanelItem, Popup, TAUIState

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> App:
    a = App(name="live-driver-test-app", version="0.1.0")

    @a.tool
    def add(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    return a


def _state_with_items() -> TAUIState:
    """State with two focusable items and no popups."""
    return TAUIState(
        panels=[
            Panel(
                id="panel.a",
                visible=True,
                items=[
                    PanelItem(id="a.1", label="A1"),
                    PanelItem(id="a.2", label="A2"),
                ],
            ),
        ],
        focused="a.1",
    )


def _dismiss_popup(popup_id: str = "popup.tool-error") -> Popup:
    """A blocking error popup with the reducer's real dismiss-action shape."""
    return Popup(
        id=popup_id,
        kind="error",
        visible=True,
        blocking=True,
        opened_by="system",
        reason="tool_failed",
        message="boom",
        actions=[Action(selector=f"{popup_id}.dismiss", input="esc", description="Dismiss")],
    )


def _accept_popup(popup_id: str = "popup.skill-suggested") -> Popup:
    """A non-blocking suggestion popup with an accept action (not a dismiss)."""
    return Popup(
        id=popup_id,
        kind="skill_suggestion",
        visible=True,
        blocking=False,
        opened_by="system",
        reason="stronger_agent_recommended",
        message="Suggested skill: x",
        actions=[
            Action(selector=f"{popup_id}.accept", input="enter", description="Adopt"),
            Action(selector=f"{popup_id}.dismiss", input="esc", description="Dismiss"),
        ],
    )


# ---------------------------------------------------------------------------
# 1. Regression — popup buttons ACT (not inert)
# ---------------------------------------------------------------------------


def test_feed_key_dismiss_popup_action_hides_and_clears_blocking(app: App) -> None:
    popup = _dismiss_popup()
    session = Session(app, state=TAUIState(popups=[popup]))
    driver = LiveDriver(session)

    driver.feed_key("esc")

    updated = next(p for p in session.state.popups if p.id == "popup.tool-error")
    assert updated.visible is False
    assert updated.blocking is False


def test_feed_key_non_dismiss_popup_action_dispatches_selector_through_session(app: App) -> None:
    popup = _accept_popup()
    session = Session(app, state=TAUIState(popups=[popup]))
    driver = LiveDriver(session)

    driver.feed_key("enter")

    assert any(
        isinstance(ev, SelectorAction) and ev.selector == "popup.skill-suggested.accept"
        for ev in session.events
    )


def test_feed_key_popup_action_returns_the_repainted_frame(app: App) -> None:
    popup = _dismiss_popup()
    session = Session(app, state=TAUIState(popups=[popup]))
    driver = LiveDriver(session)

    frame = driver.feed_key("esc")

    assert frame == driver.render()


def test_feed_key_topmost_visible_popup_wins_when_multiple_match(app: App) -> None:
    """Two visible popups both bind 'esc' to dismiss; the topmost (last) one wins."""
    bottom = _dismiss_popup("popup.bottom")
    top = _dismiss_popup("popup.top")
    session = Session(app, state=TAUIState(popups=[bottom, top]))
    driver = LiveDriver(session)

    driver.feed_key("esc")

    bottom_after = next(p for p in session.state.popups if p.id == "popup.bottom")
    top_after = next(p for p in session.state.popups if p.id == "popup.top")
    assert top_after.visible is False
    assert bottom_after.visible is True  # untouched — only the topmost match fires


# ---------------------------------------------------------------------------
# 2. Regression — no quit-trap
# ---------------------------------------------------------------------------


def test_feed_key_q_always_quits_even_with_blocking_popup_visible(app: App) -> None:
    popup = _dismiss_popup()
    session = Session(app, state=TAUIState(popups=[popup]))
    driver = LiveDriver(session)

    driver.feed_key("q")

    assert driver.running is False
    # "q" folds nothing — the blocking popup is left exactly as it was.
    assert session.state.popups[0].visible is True
    assert session.state.popups[0].blocking is True


def test_feed_key_q_works_after_dismissing_a_popup_too(app: App) -> None:
    popup = _dismiss_popup()
    session = Session(app, state=TAUIState(popups=[popup]))
    driver = LiveDriver(session)

    driver.feed_key("esc")  # dismiss first
    assert driver.running is True
    driver.feed_key("q")

    assert driver.running is False


def test_run_stops_early_once_q_is_processed(app: App) -> None:
    session = Session(app, state=_state_with_items())
    driver = LiveDriver(session)

    frames = driver.run(["down", "q", "down"])

    assert len(frames) == 2
    assert driver.running is False


def test_running_starts_true(app: App) -> None:
    session = Session(app)
    driver = LiveDriver(session)
    assert driver.running is True


# ---------------------------------------------------------------------------
# 3. Agent dispatch visibility
# ---------------------------------------------------------------------------


def test_agent_dispatch_appears_in_next_render(app: App) -> None:
    session = Session(app)
    driver = LiveDriver(session)

    driver.dispatch(SelectorAction(selector="add", args={"x": 2, "y": 3}))

    assert "✓ add: 5" in driver.render()


def test_dispatch_return_value_matches_session_state(app: App) -> None:
    session = Session(app)
    driver = LiveDriver(session)

    result_state = driver.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 1}))

    assert result_state == session.state


# ---------------------------------------------------------------------------
# 4. Plain keys route through session.feed_key
# ---------------------------------------------------------------------------


def test_plain_key_routes_through_session_feed_key(app: App) -> None:
    initial = _state_with_items()
    session = Session(app, state=initial)
    driver = LiveDriver(session)

    driver.feed_key("down")

    assert session.state.focused == "a.2"
    assert session.state == reduce(initial, KeyPress("down"))


def test_plain_key_frame_matches_default_render_ansi(app: App) -> None:
    session = Session(app, state=_state_with_items())
    driver = LiveDriver(session)

    frame = driver.feed_key("down")

    assert frame == driver.render()


def test_custom_render_callable_is_used(app: App) -> None:
    session = Session(app, state=_state_with_items())
    driver = LiveDriver(session, render=lambda s: f"focused={s.focused}")

    frame = driver.feed_key("down")

    assert frame == "focused=a.2"


# ---------------------------------------------------------------------------
# 5. Both sides share ONE session
# ---------------------------------------------------------------------------


def test_shared_session_interleaved_events_preserve_call_order(app: App) -> None:
    session = Session(app, state=_state_with_items())
    driver = LiveDriver(session)

    driver.feed_key("down")  # human
    driver.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 1}))  # agent
    driver.feed_key("up")  # human
    driver.dispatch(SelectorAction(selector="add", args={"x": 10, "y": 10}))  # agent

    kinds = [type(ev).__name__ for ev in session.events]
    assert kinds == [
        "KeyPress",
        "ToolInvoked",
        "ToolResult",
        "KeyPress",
        "ToolInvoked",
        "ToolResult",
    ]


def test_shared_session_stays_replay_equivalent_after_interleaving(app: App) -> None:
    session = Session(app, state=_state_with_items())
    driver = LiveDriver(session)

    driver.dispatch(SelectorAction(selector="add", args={"x": 1, "y": 1}))
    driver.feed_key("down")
    driver.feed_key("esc")  # no-op: no popups to dismiss
    driver.dispatch(SelectorAction(selector="add", args={"x": 2, "y": 2}))

    events = session.events
    assert replay(events[session.replay_base_index :], initial=session.initial) == session.state


def test_shared_session_single_driver_instance_sees_both_audiences(app: App) -> None:
    """A second LiveDriver wrapping the SAME session sees the first's writes."""
    session = Session(app, state=_state_with_items())
    human_driver = LiveDriver(session)
    agent_driver = LiveDriver(session)

    human_driver.feed_key("down")
    agent_driver.dispatch(SelectorAction(selector="add", args={"x": 5, "y": 5}))

    # Both drivers render the ONE shared session state — the agent's frame
    # reflects the human's earlier focus move, and vice versa.
    frame = human_driver.render()
    assert frame == agent_driver.render()
    assert session.state.focused == "a.2"
    assert "✓ add: 10" in frame
