"""Borderless, Markdown-feel ANSI renderer for the agentfront TAUI cockpit.

Why a second ANSI renderer
--------------------------
:mod:`agentfront.taui.render.ansi` draws the *boxed* cockpit (used by ``taui
render`` / snapshot / diagnose).  The interactive live cockpit wants a lighter
look (issue #45): **no box borders**, hierarchy from spacing + headings (a
Markdown feel), colour, and a **moving emoji state glyph** that animates while
a work item runs.  This module is that view.

Single source of truth
----------------------
Like :func:`agentfront.taui.render.markdown.render_markdown`, :func:`render_flat`
derives from :func:`agentfront.taui.mirror.serialize` — so the borderless ANSI
view and the Markdown view are two renders of one dict and cannot drift.  Any
new panel added to the state appears here for free.

Purity
------
:func:`render_flat` is **pure** and **deterministic**: same state → identical
output.  The "moving" glyph derives only from ``work.step_count`` (advanced by
real ``WorkStep`` events) and ``status.severity`` — no clock, no randomness, no
animation thread.  Stdlib-only.
"""

from __future__ import annotations

from typing import Any

from agentfront.taui.mirror import serialize
from agentfront.taui.render.layout import DEFAULT_WIDTH
from agentfront.taui.state import TAUIState
from agentfront.taui.widgets.prompt_input import render_prompt_input
from agentfront.taui.widgets.slash_autocomplete import format_tags

# ── local SGR helpers (no third-party rendering lib) ────────────────────────
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_CYAN = "\x1b[36m"

#: Moon-phase frames — the work-in-progress glyph cycles through these per step,
#: so the emoji visibly *moves* while a work item runs.
_WORK_FRAMES = ("🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘")

#: Steady idle glyph by status severity (motion only happens while working).
_IDLE_GLYPH = {"error": "🔴", "warn": "🟡", "success": "🟢", "info": "🟢"}


def _state_glyph(taui: dict[str, Any]) -> str:
    """The state emoji: a cycling work glyph while running, else a steady idle one."""
    work = taui.get("work") or {}
    if work.get("running"):
        return _WORK_FRAMES[int(work.get("step_count", 0)) % len(_WORK_FRAMES)]
    severity = str(taui.get("status", {}).get("severity", "info"))
    return _IDLE_GLYPH.get(severity, "🟢")


def _clip(text: str, width: int) -> str:
    """Truncate *text* to *width* display columns (approximate; borderless)."""
    if width > 0 and len(text) > width:
        return text[: max(1, width - 1)] + "…"
    return text


def _heading(title: str) -> str:
    return f"{_BOLD}{_CYAN}{title}{_RESET}"


def _state_line(taui: dict[str, Any]) -> str:
    """Top line: the moving state glyph + the status message (no box)."""
    message = str(taui.get("status", {}).get("message", ""))
    return f"{_state_glyph(taui)}  {_BOLD}{message}{_RESET}"


def _panel_block(panel: dict[str, Any], width: int) -> list[str]:
    """Render one visible panel as a borderless heading + summary + items.

    Summary lines are kept verbatim — the terminal soft-wraps them, giving the
    Markdown feel.  Only item text (which may include long descriptions) is
    truncated to keep each item on one line.
    """
    title = str(panel.get("title", panel.get("id", "")))
    summary = str(panel.get("content_summary", ""))
    items: list[dict[str, Any]] = panel.get("items", [])
    numbered = panel.get("id") == "commands"

    lines: list[str] = [_heading(title)]
    if summary:
        for raw in summary.splitlines() or [summary]:
            lines.append(f"  {_DIM}{raw}{_RESET}")
    for num, item in enumerate(items, start=1):
        label = str(item.get("label", item.get("id", "")))
        status = str(item.get("status", ""))
        tags = format_tags(item.get("tags", []))
        bullet = f"{num}." if numbered else "•"
        text = f"{label} — {status}" if status and status != "available" else label
        if tags:
            text = f"{text}  {tags}"
        lines.append(f"  {_DIM}{bullet}{_RESET} {_clip(text, max(1, width - 4))}")
    return lines


def _conversation_block(conversation: list[dict[str, Any]]) -> list[str]:
    """Render the conversation zone as a borderless heading + dim lines.

    Each entry renders as ``text`` or ``text ×N`` when ``count > 1`` —
    identical to :meth:`~agentfront.taui.state.ConversationLine.render` so the
    flat ANSI view and the Markdown view are consistent.
    """
    lines: list[str] = [_heading("Conversation")]
    for entry in conversation:
        text = str(entry.get("text", ""))
        count = int(entry.get("count", 1))
        rendered = f"{text} ×{count}" if count > 1 else text
        lines.append(f"  {_DIM}{rendered}{_RESET}")
    return lines


def _popup_block(popup: dict[str, Any], width: int) -> list[str]:
    """Render a visible popup (e.g. a failed-step error) as a flagged block."""
    message = str(popup.get("message", ""))
    lines = [f"⚠️  {_BOLD}{_clip(message, width)}{_RESET}"]
    for action in popup.get("actions", []):
        desc = str(action.get("description", "")) or str(action.get("input", ""))
        lines.append(f"  {_DIM}↳ {action.get('selector', '')} — {desc}{_RESET}")
    return lines


def render_flat(
    state: TAUIState, *, width: int = DEFAULT_WIDTH, include_prompt: bool = True
) -> str:
    """Render *state* as a borderless, colorized, Markdown-feel cockpit frame.

    Parameters
    ----------
    state:
        The current TAUI state.
    width:
        Used only for truncation (there is no right border to align to).
        Defaults to :data:`~agentfront.taui.render.layout.DEFAULT_WIDTH`.
    include_prompt:
        When ``False``, the bottom prompt line is omitted so an interactive
        session can anchor the typing cursor via :func:`input`.

    Returns a deterministic multi-line ANSI string — same *state* → same output.
    No clock, no randomness, no thread.
    """
    taui = serialize(state)
    blocks: list[list[str]] = [[_state_line(taui)]]

    for panel in taui.get("panels", []):
        # The ``slash.*`` panels carry the slash-command tree for the
        # agent-facing Markdown/TAUI tiers; the live cockpit surfaces those
        # through the ``/`` popup, so the static tree is redundant here and
        # is skipped.
        if panel.get("visible") and not str(panel.get("id", "")).startswith("slash."):
            blocks.append(_panel_block(panel, width))

    # Conversation zone — stored at the top level in the mirror dict, not
    # inside a panel, so it is rendered separately and always kept in sync
    # with render_markdown / render_ansi which both have a Conversation zone.
    conversation = taui.get("conversation", [])
    if conversation:
        blocks.append(_conversation_block(conversation))

    for popup in taui.get("popups", []):
        if popup.get("visible"):
            blocks.append(_popup_block(popup, width))

    # Sections separated by a blank line — hierarchy from spacing, not borders.
    parts = ["\n".join(block) for block in blocks]
    body = "\n\n".join(parts)

    if include_prompt:
        body += "\n\n" + render_prompt_input(state)
    return body
