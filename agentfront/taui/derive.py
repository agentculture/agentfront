"""Derive a baseline TAUIState from an App's registry.

Every tool and host command appears exactly once as a :class:`PanelItem`
with a stable dotted-path id. Aliases are recorded as ``"alias:<path>"``
tags on the canonical item, never as duplicate items.
"""

from __future__ import annotations

from agentfront.app import App
from agentfront.taui.state import Header, Panel, PanelItem, TAUIState


def make_baseline(app: App) -> TAUIState:
    """Build a registry-derived baseline :class:`TAUIState` from *app*.

    Panels are created per top-level group plus a ``"root"`` panel for
    ungrouped tools and all host commands. Items within each panel are
    sorted by id; panels are sorted by id.
    """
    header = Header(
        title=app.name,
        subtitle=app.description,
        version=app.version,
    )

    # Collect items keyed by panel id.
    panels: dict[str, list[PanelItem]] = {}

    # --- tools -----------------------------------------------------------
    for entry in app.list_tools():
        group = entry.group
        if group:
            panel_id = group[0]
        else:
            panel_id = "root"

        dotted = ".".join(group + (entry.name,))
        label = entry.description or entry.name

        tags: list[str] = []
        for alias in entry.aliases:
            alias_path = ".".join(group + (alias,))
            tags.append(f"alias:{alias_path}")

        panels.setdefault(panel_id, []).append(
            PanelItem(id=dotted, label=label, status="available", tags=tags)
        )

    # --- host commands ---------------------------------------------------
    for cmd in app.list_commands():
        tags = [f"alias:{a}" for a in cmd.aliases]
        panels.setdefault("root", []).append(
            PanelItem(id=cmd.name, label=cmd.help or cmd.name, tags=tags)
        )

    # Build sorted Panel list.
    panel_list: list[Panel] = []
    for pid in sorted(panels):
        items = sorted(panels[pid], key=lambda i: i.id)
        title = pid if pid != "root" else ""
        panel_list.append(Panel(id=pid, title=title, items=items))

    return TAUIState(header=header, panels=panel_list)
