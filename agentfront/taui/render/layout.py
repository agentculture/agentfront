"""Shared width contract for the agentfront TAUI cockpit.

A single source of truth for the box/column widths every widget and the ANSI
renderer use, so the cockpit's boxes and frame separators always *align* (they
all derive from one width) and the clamping rules live in one place.

Two regimes share these constants:

* **Headless / deterministic callers** (snapshot, ``taui render``, ``diagnose``,
  the injected driver loop, and every test) call ``render``/the widgets with the
  default ``DEFAULT_WIDTH`` — so their output is stable and reproducible.
* **Interactive callers** (foreground live-cockpit and the TTY driver) pass
  :func:`detect_width` so the cockpit fills the real terminal.

Stdlib-only (``shutil``) — zero third-party imports, matching the rest of the
TAUI package.
"""

from __future__ import annotations

import shutil

#: Default cockpit width used by every headless / deterministic caller.  Matches
#: the :func:`shutil.get_terminal_size` fallback so detection and the default
#: agree, and stays under the repo's 100-column lint limit.
DEFAULT_WIDTH = 80

#: Clamp floor.  Below this the boxes would produce negative padding / borders;
#: clamping keeps a tiny terminal degraded-but-valid rather than crashing.
MIN_WIDTH = 40

#: Fixed width of the left **skills** column when it is rendered side-by-side
#: with the conversation panel (preserves the historical skill-panel width).
SKILL_COL_WIDTH = 30

#: Number of spaces separating the two side-by-side columns.
GAP_LEN = 2


def detect_width() -> int:
    """Return the current terminal width, clamped to :data:`MIN_WIDTH`.

    Uses stdlib :func:`shutil.get_terminal_size` with a ``DEFAULT_WIDTH``
    fallback (so a non-tty / piped stdout yields the deterministic default).
    """
    cols = shutil.get_terminal_size(fallback=(DEFAULT_WIDTH, 24)).columns
    return max(MIN_WIDTH, cols)


def clip(text: str, width: int) -> str:
    """Truncate *text* to *width* display columns with a trailing ellipsis.

    Approximate (borderless) — counts code points, not display cells.  Returns
    *text* unchanged when ``width <= 0`` (no truncation) or when it already fits.
    The single home for the borderless-truncation rule the flat renderer and the
    slash-autocomplete widget share, so the two cannot drift.
    """
    if width > 0 and len(text) > width:
        return text[: max(1, width - 1)] + "…"
    return text


def clip_title(title: str, width: int) -> str:
    """Truncate a box *title* so the framed top border fits within *width*.

    A title border is ``<corner> <title> <fill…> <corner>`` — two corner cells
    plus a space on each side of the title — so the title field is at most
    ``width - 4`` cells.  Returns *title* unchanged when it already fits, clips it
    with a trailing ellipsis otherwise, and yields ``""`` when *width* is too small
    to frame any title (the box then degrades but its top border never overflows
    *width* at any normal terminal size).  The single home for the box-title
    truncation rule every boxed widget shares, so their borders stay aligned.
    """
    budget = width - 4
    if budget <= 0:
        return ""
    return clip(title, budget)
