"""TAUI reducer — a single pure fold over TAUIState.

``reduce(state, event) -> TAUIState``

The reducer is pure: it never mutates the input state and always returns a
new frozen ``TAUIState`` via ``dataclasses.replace``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from agentfront.taui.events import (
    Dismiss,
    Event,
    KeyPress,
    SelectorAction,
    SkillSuggested,
    Tick,
    UserInput,
    WorkStep,
)
from agentfront.taui.state import Action, ConversationLine, Popup, TAUIState

# ---------------------------------------------------------------------------
# Module constants (SonarCloud S1192 — avoid repeated string literals).
# ---------------------------------------------------------------------------

_ID_SKILL_SUGGESTED = "popup.skill-suggested"
_SEL_SKILL_ACCEPT = "popup.skill-suggested.accept"
_SEL_SKILL_DISMISS = "popup.skill-suggested.dismiss"
_KIND_SKILL_SUGGESTION = "skill_suggestion"
_ID_WORK_ERROR = "popup.work-error"
_SEL_WORK_ERROR_DISMISS = "popup.work-error.dismiss"
_KIND_ERROR = "error"
_REASON_WORK_STEP_FAILED = "work_step_failed"
_MSG_WORK_STEP_FAILED_DEFAULT = "Work step failed"


def _replace(state: TAUIState, **changes: Any) -> TAUIState:
    """Typed wrapper around :func:`dataclasses.replace` for :class:`TAUIState`."""
    return cast(TAUIState, replace(state, **changes))


def append_conversation(lines: list[ConversationLine], text: str) -> list[ConversationLine]:
    """Append *text* to *lines* with consecutive-duplicate collapse.

    If the last line already has the same text, its count is incremented
    rather than adding a new entry.
    """
    if lines and lines[-1].text == text:
        last = lines[-1]
        return [*lines[:-1], replace(last, count=last.count + 1)]
    return [*lines, ConversationLine(text=text)]


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

    v1 scope is **navigation parity**: this single fold moves focus and toggles
    popup visibility, and an agent ``SelectorAction(sel)`` reaches the same
    state as the human ``KeyPress`` navigation to ``sel``. Tool *execution*
    (via ``SelectorAction.args``) and keyboard-reachable popup actions are
    deferred to the live-driver work, so the agent/human equivalence here is
    over the navigation/visibility fold, not invocation.
    """
    if isinstance(event, KeyPress):
        return _reduce_key(state, event.key)
    if isinstance(event, SelectorAction):
        return _reduce_selector(state, event.selector)
    if isinstance(event, Dismiss):
        return _reduce_dismiss(state)
    if isinstance(event, Tick):
        new_bg = replace(state.background, frame=state.background.frame + event.delta)
        return _replace(state, background=new_bg)
    if isinstance(event, UserInput):
        return _replace(state, conversation=append_conversation(state.conversation, event.text))
    if isinstance(event, SkillSuggested):
        popup = Popup(
            id=_ID_SKILL_SUGGESTED,
            kind=_KIND_SKILL_SUGGESTION,
            visible=True,
            blocking=False,
            opened_by="system",
            reason=event.reason,
            message=(f"Suggested skill: {event.skill}" if event.skill else "Skill suggested"),
            actions=[
                Action(selector=_SEL_SKILL_ACCEPT, input="enter", description="Adopt suggestion"),
                Action(selector=_SEL_SKILL_DISMISS, input="esc", description="Dismiss"),
            ],
        )
        new_bg = replace(state.background, theme=event.theme, semantic=event.semantic)
        return _replace(state, popups=[*state.popups, popup], background=new_bg)
    if isinstance(event, WorkStep):
        conv = append_conversation(state.conversation, event.label)
        work = state.work_item
        if work is not None:
            work = replace(work, step_count=work.step_count + 1)
        popups = state.popups
        if not event.ok:
            err = Popup(
                id=_ID_WORK_ERROR,
                kind=_KIND_ERROR,
                visible=True,
                blocking=True,
                opened_by="system",
                reason=_REASON_WORK_STEP_FAILED,
                message=(event.error or event.label or _MSG_WORK_STEP_FAILED_DEFAULT),
                actions=[
                    Action(
                        selector=_SEL_WORK_ERROR_DISMISS,
                        input="esc",
                        description="Dismiss",
                    )
                ],
            )
            # Refresh a single live error popup rather than appending a duplicate
            # id on every failed step (repeated failures are normal in a work
            # loop; duplicate ids would trip the LAYOUT diagnose check).
            if any(p.id == _ID_WORK_ERROR for p in popups):
                popups = [err if p.id == _ID_WORK_ERROR else p for p in popups]
            else:
                popups = [*popups, err]
        return _replace(state, conversation=conv, work_item=work, popups=popups)
    # Unknown event → no-op
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
    return _replace(state, focused=order[new_idx])


# ---------------------------------------------------------------------------
# SelectorAction handler
# ---------------------------------------------------------------------------


def _reduce_selector(state: TAUIState, selector: str) -> TAUIState:
    """Set focused to *selector* if it is in the focus order."""
    if selector in focus_order(state):
        return _replace(state, focused=selector)
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

    # Build new popups list with the target hidden. A dismissed popup is no
    # longer blocking — clearing it keeps the POPUP_LIFECYCLE invariant
    # ("a blocking popup must be visible") true for normally-dismissed modals.
    new_popups: list[Popup] = []
    for i, popup in enumerate(popups):
        if i == target_idx:
            new_popups.append(cast(Popup, replace(popup, visible=False, blocking=False)))
        else:
            new_popups.append(popup)

    return _replace(state, popups=new_popups)


# ---------------------------------------------------------------------------
# Event replay
# ---------------------------------------------------------------------------


def replay(events: list[Event], initial: TAUIState | None = None) -> TAUIState:
    """Fold an event trail back into a state.

    *initial* defaults to a bare :class:`~agentfront.taui.state.TAUIState`
    when ``None``.  Pure: does not mutate *events* or *initial*.
    """
    state = initial if initial is not None else TAUIState()
    for ev in events:
        state = reduce(state, ev)
    return state
