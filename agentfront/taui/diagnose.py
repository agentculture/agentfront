"""TAUI diagnose — cross-render invariant checker.

Checks that the JSON mirror, ANSI render, and markdown render all agree on
the structural content derived from ONE :class:`~agentfront.taui.state.TAUIState`.

Public API
---------
DiagnoseResult
diagnose
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentfront.taui.mirror import serialize
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.selectors import all_selectors_resolve, resolve
from agentfront.taui.state import TAUIState


@dataclass(frozen=True)
class DiagnoseResult:
    """Result of a cross-render diagnosis."""

    ok: bool
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "problems": list(self.problems)}


def diagnose(
    state: TAUIState,
    *,
    mirror: dict[str, Any] | None = None,
    ansi: str | None = None,
    markdown: str | None = None,
) -> DiagnoseResult:
    """Check cross-render invariants for *state*.

    When an argument is ``None``, it is computed from *state* via the
    corresponding renderer.  Supplying a pre-computed (possibly desynced)
    value lets callers test disagreement detection.

    Checks performed (each failure appends a problem string):

    1. :func:`~agentfront.taui.selectors.all_selectors_resolve` is ``True``.
    2. Every selector in ``mirror["available_actions"]`` resolves via
       :func:`~agentfront.taui.selectors.resolve`.
    3. For every visible panel item, its label appears in both *ansi* and
       *markdown*.
    4. The focused selector resolves via :func:`~agentfront.taui.selectors.resolve`.

    Returns a :class:`DiagnoseResult` with ``ok=True`` when no problems were
    found.
    """
    if mirror is None:
        mirror = serialize(state)
    if ansi is None:
        ansi = render_ansi(state)
    if markdown is None:
        markdown = render_markdown(state)

    problems: list[str] = []

    # 1. All advertised selectors must resolve.
    if not all_selectors_resolve(state):
        problems.append("Not all advertised selectors resolve")

    # 2. Every available_actions selector must resolve.
    for entry in mirror.get("available_actions", []):
        sel = entry.get("selector")
        if sel is not None:
            try:
                resolve(state, sel)
            except Exception as exc:
                problems.append(f"available_actions selector {sel!r} does not resolve: {exc}")

    # 3. Every visible panel item label must appear in both renders.
    for panel in state.panels:
        if not panel.visible:
            continue
        for item in panel.items:
            label = item.label
            if label not in ansi:
                problems.append(f"Visible item label {label!r} missing from ANSI render")
            if label not in markdown:
                problems.append(f"Visible item label {label!r} missing from markdown render")

    # 4. The focused selector must resolve.
    try:
        resolve(state, state.focused)
    except Exception as exc:
        problems.append(f"Focused selector {state.focused!r} does not resolve: {exc}")

    return DiagnoseResult(ok=len(problems) == 0, problems=problems)
