"""Markdown renderer for TAUIState — deterministic, stdlib-only."""

from __future__ import annotations

from agentfront.taui.state import TAUIState


def render_markdown(state: TAUIState) -> str:
    """Render a TAUIState as a deterministic, human-readable markdown string.

    Produces:
    - A top-level ``# {header.title}`` heading (with version/subtitle line).
    - A ``## Status`` section derived from ``state.status``.
    - For each visible panel a ``## {panel.title}`` heading followed by a
      markdown list of its items (``- {label} ({status})``), marking the
      focused item (``id == state.focused``) with ``**(focused)**``.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# {state.header.title}")
    meta_parts = []
    if state.header.version:
        meta_parts.append(state.header.version)
    if state.header.subtitle:
        meta_parts.append(state.header.subtitle)
    if meta_parts:
        lines.append(" — ".join(meta_parts))
    lines.append("")

    # Status
    lines.append("## Status")
    lines.append(f"{state.status.severity}: {state.status.message}")
    lines.append("")

    # Panels
    for panel in state.panels:
        if not panel.visible:
            continue
        lines.append(f"## {panel.title}")
        for item in panel.items:
            focused_marker = " **(focused)**" if item.id == state.focused else ""
            lines.append(f"- {item.label} ({item.status}){focused_marker}")
        lines.append("")

    # Conversation section (only when non-empty)
    if state.conversation:
        lines.append("## Conversation")
        lines.append("")
        for conv_line in state.conversation:
            lines.append(f"- {conv_line.render()}")
        lines.append("")

    return "\n".join(lines)
