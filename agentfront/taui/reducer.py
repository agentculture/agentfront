"""TAUI reducer — a single pure fold over TAUIState.

``reduce(state, event) -> TAUIState``

The reducer is pure: it never mutates the input state and always returns a
new frozen ``TAUIState`` via ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import replace

from agentfront.taui.events import (
    Dismiss,
    Event,
    KeyPress,
    SelectorAction,
)
from agentfront.taui.state import Popup, TAUIState


def focus_order(state: TAUIState) -> list[str]:
    """Return the deterministic focus order for *state*.

    Visible panel items first (in panel order), then the input prompt.
    """
    ids: list[str] = []
    for panel in state.panels:
        if panel.visible:
            for item in panel.items:
                ids.append(item.id)
    ids.append("input.prompt")
    return ids


def reduce(state: TAUIState, event: Event) -> TAUIState:
    """Pure reducer: ``state`` + ``event`` → new ``TAUIState``.

    Never mutates *state*; always returns a (possibly equal) new instance.
    """
    if isinstance(event, KeyPress):
        return _reduce_key(state, event.key)
    if isinstance(event, SelectorAction):
        return _reduce_selector(state, event.selector)
    if isinstance(event, Dismiss):
        return _reduce_dismiss(state)
    # Tick, UserInput, or any other event → no-op
    return state


# ---------------------------------------------------------------------------
# KeyPress handlers
# ---------------------------------------------------------------------------


def _reduce_key(state: TAUIState, key: str) -> TAUIState:
    if key == "down":
        return _navigate(state, +1)
    if key == "up":
        return _navigate(state, -1)
    if key == "esc":
        return _reduce_dismiss(state)
    # "enter" and any other key → no-op for v1
    return state


def _navigate(state: TAUIState, direction: int) -> TAUIState:
    """Move *state.focused* by *direction* steps within ``focus_order``."""
    order = focus_order(state)
    if not order:
        return state

    current = state.focused
    try:
        idx = order.index(current)
    except ValueError:
        # Current focus not in order → jump to first
        idx = 0

    new_idx = idx + direction
    new_idx = max(0, min(len(order) - 1, new_idx))
    return replace(state, focused=order[new_idx])


# ---------------------------------------------------------------------------
# SelectorAction handler
# ---------------------------------------------------------------------------


def _reduce_selector(state: TAUIState, selector: str) -> TAUIState:
    """Set focused to *selector* if it is in the focus order."""
    if selector in focus_order(state):
        return replace(state, focused=selector)
    return state


# ---------------------------------------------------------------------------
# Dismiss handler
# ---------------------------------------------------------------------------


def _reduce_dismiss(state: TAUIState) -> TAUIState:
    """Hide the topmost visible popup."""
    popups = state.popups
    # Find the last visible popup (topmost)
    target_idx = None
    for i in range(len(popups) - 1, -1, -1):
        if popups[i].visible:
            target_idx = i
            break

    if target_idx is None:
        return state

    # Build new popups list with the target hidden
    new_popups: list[Popup] = []
    for i, popup in enumerate(popups):
        if i == target_idx:
            new_popups.append(replace(popup, visible=False))
        else:
            new_popups.append(popup)

    return replace(state, popups=new_popups)
