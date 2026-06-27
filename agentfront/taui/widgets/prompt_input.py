"""Prompt-input widget — renders the bottom prompt line.

The prompt is a clean ``{context} ❯`` chevron — the context word names the tool
you are interacting with, and ``❯`` signals "type here". When
``state.focused == "input.prompt"`` it renders bright; otherwise dim.

The spinner character is derived deterministically from
``state.background.frame % 4`` when ``state.background.animation`` is set and not
``"none"`` — so the output is clock-free and random-free.

:func:`plain_prompt` returns the same prompt text *without* ANSI escapes — an
interactive session can pass it to :func:`input` so the typing cursor anchors right
after ``{context} ❯`` (escapes in an ``input`` prompt confuse readline's cursor
math, so the plain form is used there).

The context word is generic: ``render_prompt_input`` uses ``context`` if supplied,
else falls back to ``state.header.title`` (or ``"agent"`` when the title is empty).
This lets a consumer override the word explicitly while the application's own header
drives it by default — no hard-coded tool name.
"""

from __future__ import annotations

from agentfront.taui.state import TAUIState

_SPINNER_CHARS = "|/-\\"
_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BRIGHT = "\x1b[1m"


def plain_prompt(context: str = "agent") -> str:
    """Return the prompt text with no ANSI escapes (for :func:`input`).

    *context* is the word that appears before ``❯`` (e.g. ``"agent"``,
    ``"agentfront"``). Defaults to ``"agent"``.
    """
    return f"{context} ❯ "


def render_prompt_input(state: TAUIState, *, context: str | None = None) -> str:
    """Return the prompt input line as a string.

    The context word is *context* if supplied, else ``state.header.title``
    (falling back to ``"agent"`` when the title is empty). This lets a consumer
    override the word explicitly while the application header drives it by default.

    Brightness reflects focus: bright when ``state.focused == "input.prompt"``,
    dim otherwise. A spinner character (from ``"|/-\\"``) is derived from
    ``state.background.frame % 4`` only when ``state.background.animation`` is
    set and not ``"none"`` — so the output is deterministic and clock-free.
    """
    ctx = context if context is not None else (state.header.title or "agent")
    focused = state.focused == "input.prompt"

    # Spinner: only when animation is active (non-empty and not the "none" sentinel).
    if state.background.animation and state.background.animation != "none":
        spinner = _SPINNER_CHARS[state.background.frame % 4]
        spinner_str = f"{spinner} "
    else:
        spinner_str = ""

    weight = _BRIGHT if focused else _DIM
    return f"{weight}{ctx} ❯{_RESET} {spinner_str}".rstrip() + " "
