"""ANSI renderer for TAUIState — deterministic, stdlib-only."""

from __future__ import annotations

from agentfront.taui.state import TAUIState


def render_ansi(state: TAUIState) -> str:
    """Render a deterministic terminal frame from *state*.

    The output is byte-identical for the same state: no clock, no randomness,
    no third-party imports.
    """
    lines: list[str] = []

    # Header line
    parts: list[str] = [state.header.title]
    if state.header.version:
        parts.append(state.header.version)
    if state.header.subtitle:
        parts.append(state.header.subtitle)
    lines.append(" — ".join(parts))
    lines.append("")

    # Panels (only visible ones)
    for panel in state.panels:
        if not panel.visible:
            continue
        lines.append(f"## {panel.title}")
        for item in panel.items:
            prefix = "> " if item.id == state.focused else "  "
            lines.append(f"{prefix}{item.label} [{item.status}]")
        lines.append("")

    # Status line
    lines.append(f"[{state.status.severity}] {state.status.message}")

    return "\n".join(lines)
