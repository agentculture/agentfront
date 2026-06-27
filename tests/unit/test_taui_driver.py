"""Unit tests for agentfront.taui.driver — the thin reference TTY driver."""

from __future__ import annotations

import functools

from agentfront.taui.driver import Driver, drive
from agentfront.taui.events import KeyPress
from agentfront.taui.reducer import reduce
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.state import Panel, PanelItem, TAUIState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_with_items() -> TAUIState:
    """State with three focusable items across two panels."""
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
            Panel(
                id="panel.b",
                visible=True,
                items=[PanelItem(id="b.1", label="B1")],
            ),
        ],
        focused="a.1",
    )


# ---------------------------------------------------------------------------
# feed_key
# ---------------------------------------------------------------------------


def test_feed_key_updates_state() -> None:
    """feed_key applies reduce(state, KeyPress(key)) and updates internal state."""
    state = _state_with_items()
    driver = Driver(state)
    driver.feed_key("down")
    assert driver.state.focused == "a.2"


def test_feed_key_returns_repaint() -> None:
    """feed_key returns render_ansi of the post-reduce state."""
    state = _state_with_items()
    driver = Driver(state)
    frame = driver.feed_key("down")
    assert frame == render_ansi(driver.state)


def test_feed_key_no_real_tty() -> None:
    """The driver runs fully from a Python list with no TTY."""
    state = _state_with_items()
    driver = Driver(state)
    # This call must succeed without any terminal attached.
    frames = driver.run(["down", "down", "up"])
    assert len(frames) == 3


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def test_run_yields_frames() -> None:
    """run(keys) returns one frame per key."""
    state = _state_with_items()
    driver = Driver(state)
    frames = driver.run(["down", "down"])
    assert len(frames) == 2


def test_run_final_state_matches_reduce_fold() -> None:
    """Driver(state).run(keys) leaves driver.state equal to
    functools.reduce(reduce, [KeyPress(k) for k in keys], state).
    """
    state = _state_with_items()
    keys = ["down", "down", "up", "down", "esc"]

    driver = Driver(state)
    driver.run(keys)

    events = [KeyPress(k) for k in keys]
    expected = functools.reduce(reduce, events, state)

    assert driver.state.to_dict() == expected.to_dict()


# ---------------------------------------------------------------------------
# drive convenience
# ---------------------------------------------------------------------------


def test_drive_returns_final_state() -> None:
    """drive(state, keys) returns the final state after folding all keys."""
    state = _state_with_items()
    keys = ["down", "down"]

    final = drive(state, keys)

    events = [KeyPress(k) for k in keys]
    expected = functools.reduce(reduce, events, state)

    assert final.to_dict() == expected.to_dict()


# ---------------------------------------------------------------------------
# state property
# ---------------------------------------------------------------------------


def test_state_property_exposes_current_state() -> None:
    """driver.state exposes the current TAUIState."""
    state = _state_with_items()
    driver = Driver(state)
    assert driver.state is state


def test_state_property_updates_after_feed() -> None:
    """driver.state reflects the updated state after feed_key."""
    state = _state_with_items()
    driver = Driver(state)
    driver.feed_key("down")
    assert driver.state.focused == "a.2"


# ---------------------------------------------------------------------------
# Custom render
# ---------------------------------------------------------------------------


def test_custom_render() -> None:
    """Driver accepts a custom render callable."""
    state = _state_with_items()
    driver = Driver(state, render=lambda s: f"focused={s.focused}")
    frame = driver.feed_key("down")
    assert frame == "focused=a.2"
