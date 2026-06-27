"""Command-palette widget — renders the ``"commands"`` panel from ``TAUIState.panels``.

The panel with ``id == "commands"`` lists its items as a **numbered** menu —
the number is the operator's selector to run a template.

Returns ``""`` when no ``"commands"`` panel is present or it is not visible.
"""

from __future__ import annotations

from agentfront.taui.render.layout import DEFAULT_WIDTH, clip_title
from agentfront.taui.state import TAUIState

_BORDER = "─"


def _hline(width: int, title: str = "") -> str:
    if title:
        inner = f" {clip_title(title, width)} "
        pad = max(0, width - len(inner) - 2)
        return "┌" + inner + _BORDER * pad + "┐"
    return "└" + _BORDER * (width - 2) + "┘"


def render_command_palette(state: TAUIState, *, width: int = DEFAULT_WIDTH) -> str:
    """Return a box-drawn, numbered command palette, or ``""`` if absent/hidden."""
    panel = next((p for p in state.panels if p.id == "commands"), None)
    if panel is None or not panel.visible:
        return ""

    max_inner = max(1, width - 4)
    lines: list[str] = [_hline(width, panel.title or "Work templates")]
    if panel.content_summary:
        lines.append(f"│ {panel.content_summary[:max_inner]:<{max_inner}} │")

    # "│ NN. <label> │" — leave room for the 2-wide number, dot, and the borders.
    max_label = max(1, width - 8)
    for num, item in enumerate(panel.items, start=1):
        label = item.label
        if len(label) > max_label:
            label = label[: max_label - 1] + "…"
        lines.append(f"│ {num:>2}. {label:<{max_label}} │")

    lines.append(_hline(width))
    return "\n".join(lines)
