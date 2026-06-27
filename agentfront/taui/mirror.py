"""TAUI mirror — serialize state to the JSON mirror dict (agent's view).

The mirror is the agent-facing representation of the TUI state.  It starts
from :meth:`TAUIState.to_dict` and augments it with ``taui_version`` and
``available_actions`` derived directly from the state tree so the invariant
holds: every selector in ``available_actions`` resolves via
:func:`~agentfront.taui.selectors.resolve`.
"""

from __future__ import annotations

from typing import Any

from agentfront.taui.selectors import resolve
from agentfront.taui.state import TAUIState

SCHEMA_VERSION: str = "0.1"


def serialize(state: TAUIState) -> dict[str, Any]:
    """Serialize *state* to the JSON mirror dict.

    The result starts from :meth:`TAUIState.to_dict` and adds:

    - ``taui_version`` — the schema version string.
    - ``available_actions`` — a flat list derived from the state tree:
        * each visible panel's items become ``{"selector": ..., "input": "select", ...}``
        * each visible popup's actions become ``{"selector": ..., "input": ..., ...}``
        * the standing ``input.prompt`` action is always appended.

    Every selector in ``available_actions`` resolves via
    :func:`~agentfront.taui.selectors.resolve` on *state*.
    """
    result: dict[str, Any] = state.to_dict()
    result["taui_version"] = SCHEMA_VERSION

    actions: list[dict[str, str]] = []

    # Visible panels -> their items.
    for panel in state.panels:
        if not panel.visible:
            continue
        for item in panel.items:
            actions.append(
                {
                    "selector": item.id,
                    "input": "select",
                    "description": item.label,
                    "status": item.status,
                }
            )

    # Visible popups -> their actions.
    for popup in state.popups:
        if not popup.visible:
            continue
        for action in popup.actions:
            actions.append(
                {
                    "selector": action.selector,
                    "input": action.input,
                    "description": action.description,
                }
            )

    # Standing selector.
    actions.append(
        {
            "selector": "input.prompt",
            "input": "type",
            "description": "Send instruction to current agent",
        }
    )

    result["available_actions"] = actions

    # Invariant check: every selector must resolve.
    for entry in actions:
        resolve(state, entry["selector"])

    return result
