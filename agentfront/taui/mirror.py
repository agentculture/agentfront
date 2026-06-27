"""TAUI mirror — serialize state to the JSON mirror dict (agent's view).

The mirror is the agent-facing representation of the TUI state.  It starts
from :meth:`TAUIState.to_dict` and augments it with ``taui_version`` and
``available_actions`` derived directly from the state tree, so every selector
in ``available_actions`` resolves *by construction*.
:func:`agentfront.taui.diagnose.diagnose` validates that cross-render
invariant; ``serialize`` itself is a pure projection that never raises on a
valid :class:`TAUIState`.
"""

from __future__ import annotations

from typing import Any

from agentfront.taui.state import TAUIState

SCHEMA_VERSION: str = "0.2"


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

    # Every selector above is taken from a real node in the state tree
    # (panel item id, popup action selector, or the standing input prompt), so
    # it resolves by construction. diagnose() is the validator for the broader
    # cross-render invariant; serialize() stays a pure, non-throwing projection.
    return result
