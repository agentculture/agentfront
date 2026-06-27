"""Conversation widget — renders ``TAUIState.conversation`` as a box-drawn panel.

The conversation is stored directly on the state as a list of
:class:`~agentfront.taui.state.ConversationLine` objects (not in a panel).
Each line's ``.render()`` method returns the display text, or ``"text ×N"``
when a consecutive duplicate has been collapsed (``count > 1``).

Returns an empty string when ``state.conversation`` is empty.
"""

from __future__ import annotations

from agentfront.taui.render.layout import DEFAULT_WIDTH
from agentfront.taui.state import TAUIState

_BORDER = "─"


def _hline(width: int, title: str = "") -> str:
    if title:
        inner = f" {title} "
        pad = max(0, width - len(inner) - 2)
        return "╔" + inner + _BORDER * pad + "╗"
    return "╚" + _BORDER * (width - 2) + "╝"


def render_conversation(state: TAUIState, *, width: int = DEFAULT_WIDTH) -> str:
    """Return a box-drawn conversation panel string, or ``""`` if empty.

    Reads lines from ``state.conversation`` (a list of
    :class:`~agentfront.taui.state.ConversationLine`).  Each line's
    ``.render()`` method provides the display text (plain or ``text ×N``).

    *width* is the full box width; the wrap point is ``width - 4`` inner chars,
    so a wider box wraps later.  The clamp ``max(1, width - 4)`` prevents a
    negative field width or a non-shrinking wrap chunk on pathologically small
    widths.
    """
    if not state.conversation:
        return ""

    # Clamp to >=1 so a pathologically small width can never produce a negative
    # field width (format error) or a non-shrinking wrap chunk (infinite loop).
    max_inner = max(1, width - 4)
    lines: list[str] = [_hline(width, "Conversation")]

    for conv_line in state.conversation:
        row = conv_line.render()
        # Wrap each logical line at the inner width; pad the tail for clean edges.
        while len(row) > max_inner:
            lines.append(f"║ {row[:max_inner]} ║")
            row = row[max_inner:]
        lines.append(f"║ {row:<{max_inner}} ║")

    lines.append(_hline(width))
    return "\n".join(lines)
