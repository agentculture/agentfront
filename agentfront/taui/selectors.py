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

from agentfront.errors import AgentfrontError, EXIT_USER_ERROR
from agentfront.taui.state import TAUIState

# Sentinel returned for the standing selector "input.prompt".
_INPUT_SENTINEL: dict[str, str] = {"kind": "input", "selector": "input.prompt"}


def resolve(state: TAUIState, selector: str) -> Any:
    """Resolve *selector* to the corresponding node in *state*.

    Returns the matched :class:`Panel`, :class:`PanelItem`, :class:`Popup`,
    :class:`Action`, or the input sentinel dict for ``"input.prompt"``.

    Raises :class:`~agentfront.errors.AgentfrontError` with
    ``code == EXIT_USER_ERROR`` when the selector is unknown.
    """
    # Standing selector.
    if selector == "input.prompt":
        return _INPUT_SENTINEL

    # Panels.
    for panel in state.panels:
        if panel.id == selector:
            return panel
        # Panel items (dotted ids like "feedback.record").
        for item in panel.items:
            if item.id == selector:
                return item
            # Alias tags: "alias:<path>" -> resolve by <path>.
            for tag in item.tags:
                if tag.startswith("alias:"):
                    alias_path = tag[len("alias:") :]
                    if alias_path == selector:
                        return item

    # Popups.
    for popup in state.popups:
        if popup.id == selector:
            return popup
        # Popup actions.
        for action in popup.actions:
            if action.selector == selector:
                return action

    raise AgentfrontError(
        code=EXIT_USER_ERROR,
        message=f"Unknown selector: {selector!r}",
        remediation=(
            "Check the selector string; " "use advertised_selectors() to list valid selectors."
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
                if tag.startswith("alias:"):
                    selectors.append(tag[len("alias:") :])

    # Popup ids.
    for popup in state.popups:
        selectors.append(popup.id)
        # Popup action selectors.
        for action in popup.actions:
            selectors.append(action.selector)

    # Standing selector.
    selectors.append("input.prompt")

    return selectors


def all_selectors_resolve(state: TAUIState) -> bool:
    """Return ``True`` iff :func:`resolve` succeeds for every advertised selector."""
    for sel in advertised_selectors(state):
        try:
            resolve(state, sel)
        except AgentfrontError:
            return False
    return True
