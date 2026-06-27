"""TAUI selectors — resolve a string selector to a node in the state tree.

A *selector* is a stable string that addresses a node (Panel, PanelItem,
Popup, or Action) in a :class:`~agentfront.taui.state.TAUIState`.  The
standing selector ``"input.prompt"`` resolves to a sentinel dict.

Public API
---------
resolve(state, selector) -> node
advertised_selectors(state) -> list[str]
all_selectors_resolve(state) -> bool
"""

from __future__ import annotations

from typing import Any

from agentfront.errors import EXIT_USER_ERROR, AgentfrontError
from agentfront.taui.state import PanelItem, TAUIState

# Module constants (SonarCloud S1192).
_INPUT_PROMPT = "input.prompt"
_ALIAS_PREFIX = "alias:"

# Sentinel returned for the standing selector "input.prompt".
_INPUT_SENTINEL: dict[str, str] = {"kind": "input", "selector": _INPUT_PROMPT}


def _item_matches(item: PanelItem, selector: str) -> bool:
    """True if *item* is addressed by *selector* directly or via an alias tag."""
    if item.id == selector:
        return True
    # An alias tag is exactly "alias:<selector>" — compare the whole string
    # rather than slicing (slice-and-compare trips SonarCloud S6659).
    for tag in item.tags:
        if tag == _ALIAS_PREFIX + selector:
            return True
    return False


def _resolve_in_panels(state: TAUIState, selector: str) -> Any:
    """Return the matching Panel, PanelItem, or None from *state.panels*."""
    for panel in state.panels:
        if panel.id == selector:
            return panel
        for item in panel.items:
            if _item_matches(item, selector):
                return item
    return None


def _resolve_in_popups(state: TAUIState, selector: str) -> Any:
    """Return the matching Popup, Action, or None from *state.popups*."""
    for popup in state.popups:
        if popup.id == selector:
            return popup
        for action in popup.actions:
            if action.selector == selector:
                return action
    return None


def resolve(state: TAUIState, selector: str) -> Any:
    """Resolve *selector* to the corresponding node in *state*.

    Returns the matched :class:`Panel`, :class:`PanelItem`, :class:`Popup`,
    :class:`Action`, or the input sentinel dict for ``"input.prompt"``.

    Raises :class:`~agentfront.errors.AgentfrontError` with
    ``code == EXIT_USER_ERROR`` when the selector is unknown.
    """
    # Standing selector.
    if selector == _INPUT_PROMPT:
        return _INPUT_SENTINEL

    # Panels (panels -> items -> aliases).
    node = _resolve_in_panels(state, selector)
    if node is not None:
        return node

    # Popups (popups -> actions).
    node = _resolve_in_popups(state, selector)
    if node is not None:
        return node

    raise AgentfrontError(
        code=EXIT_USER_ERROR,
        message=f"Unknown selector: {selector!r}",
        remediation=(
            "Check the selector string; use advertised_selectors() to list valid selectors."
        ),
    )


def advertised_selectors(state: TAUIState) -> list[str]:
    """Return every selector that :func:`resolve` can successfully resolve."""
    selectors: list[str] = []

    # Panel ids.
    for panel in state.panels:
        selectors.append(panel.id)
        # Panel item ids.
        for item in panel.items:
            selectors.append(item.id)
            # Alias paths.
            for tag in item.tags:
                if tag.startswith(_ALIAS_PREFIX):
                    selectors.append(tag[len(_ALIAS_PREFIX) :])

    # Popup ids.
    for popup in state.popups:
        selectors.append(popup.id)
        # Popup action selectors.
        for action in popup.actions:
            selectors.append(action.selector)

    # Standing selector.
    selectors.append(_INPUT_PROMPT)

    return selectors


def all_selectors_resolve(state: TAUIState) -> bool:
    """Return ``True`` iff :func:`resolve` succeeds for every advertised selector."""
    for sel in advertised_selectors(state):
        try:
            resolve(state, sel)
        except AgentfrontError:
            return False
    return True
