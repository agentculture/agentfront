"""TAUI diagnose — cross-render invariant checker.

Checks that the JSON mirror, ANSI render, and markdown render all agree on
the structural content derived from ONE :class:`~agentfront.taui.state.TAUIState`.

Public API
---------
DiagnoseResult
diagnose
BUG_CLASSES
Finding
Diagnosis
diagnose_structured
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentfront.taui.mirror import serialize
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.selectors import all_selectors_resolve, resolve
from agentfront.taui.state import TAUIState

# Bug-class name constants (SonarCloud S1192 — avoid repeated literals).
_BC_STATE = "STATE"
_BC_RENDER = "RENDER"
_BC_LAYOUT = "LAYOUT"
_BC_FOCUS = "FOCUS"
_BC_INPUT_ROUTING = "INPUT_ROUTING"
_BC_THEME = "THEME"
_BC_POPUP_LIFECYCLE = "POPUP_LIFECYCLE"

BUG_CLASSES = (
    _BC_STATE,
    _BC_RENDER,
    _BC_LAYOUT,
    _BC_FOCUS,
    _BC_INPUT_ROUTING,
    _BC_THEME,
    _BC_POPUP_LIFECYCLE,
)


@dataclass(frozen=True)
class DiagnoseResult:
    """Result of a cross-render diagnosis."""

    ok: bool
    problems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "problems": list(self.problems)}


def _check_all_selectors_resolve(state: TAUIState) -> list[str]:
    """Every advertised selector must resolve."""
    if not all_selectors_resolve(state):
        return ["Not all advertised selectors resolve"]
    return []


def _check_available_actions_resolve(state: TAUIState, mirror: dict[str, Any]) -> list[str]:
    """Every ``available_actions`` selector in the mirror must resolve."""
    problems: list[str] = []
    for entry in mirror.get("available_actions", []):
        sel = entry.get("selector")
        if sel is None:
            continue
        try:
            resolve(state, sel)
        except Exception as exc:
            problems.append(f"available_actions selector {sel!r} does not resolve: {exc}")
    return problems


def _check_labels_in_renders(state: TAUIState, ansi: str, markdown: str) -> list[str]:
    """Every visible panel item's label must appear in both renders."""
    problems: list[str] = []
    for panel in state.panels:
        if not panel.visible:
            continue
        for item in panel.items:
            if item.label not in ansi:
                problems.append(f"Visible item label {item.label!r} missing from ANSI render")
            if item.label not in markdown:
                problems.append(f"Visible item label {item.label!r} missing from markdown render")
    return problems


def _check_focused_resolves(state: TAUIState) -> list[str]:
    """The focused selector must resolve."""
    try:
        resolve(state, state.focused)
    except Exception as exc:
        return [f"Focused selector {state.focused!r} does not resolve: {exc}"]
    return []


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
    problems += _check_all_selectors_resolve(state)
    problems += _check_available_actions_resolve(state, mirror)
    problems += _check_labels_in_renders(state, ansi, markdown)
    problems += _check_focused_resolves(state)
    return DiagnoseResult(ok=not problems, problems=problems)


# ---------------------------------------------------------------------------
# Structured layer — Finding / Diagnosis / diagnose_structured
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """A single structured diagnostic finding."""

    bug_class: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"bug_class": self.bug_class, "message": self.message}


@dataclass(frozen=True)
class Diagnosis:
    """Structured result of a cross-render diagnosis."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there are no findings."""
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [f.to_dict() for f in self.findings]}

    def by_class(self, bug_class: str) -> list[Finding]:
        """Return all findings for a specific bug class."""
        return [f for f in self.findings if f.bug_class == bug_class]


def diagnose_structured(
    state: TAUIState,
    *,
    mirror: dict[str, Any] | None = None,
    ansi: str | None = None,
    markdown: str | None = None,
) -> Diagnosis:
    """Check cross-render invariants and return a structured :class:`Diagnosis`.

    Computes mirror/ansi/markdown from *state* when not supplied.  Supplying
    pre-computed (possibly desynced) values lets callers test disagreement
    detection.

    Every check is conservative: a clean :class:`TAUIState` yields ``ok=True``
    (zero findings).

    Bug classes checked:

    - **STATE** — JSON round-trip fidelity.
    - **FOCUS** — focused selector resolution.
    - **INPUT_ROUTING** — advertised and available_actions selector resolution.
    - **RENDER** — visible panel item labels and conversation lines in renders.
    - **LAYOUT** — duplicate panel or popup ids.
    - **THEME** — background semantic/theme/frame coherence.
    - **POPUP_LIFECYCLE** — blocking-popup visibility invariant.
    """
    if mirror is None:
        mirror = serialize(state)
    if ansi is None:
        ansi = render_ansi(state)
    if markdown is None:
        markdown = render_markdown(state)

    findings: list[Finding] = []

    # STATE: JSON round-trip fidelity.
    if TAUIState.from_dict(state.to_dict()) != state:
        findings.append(Finding(_BC_STATE, "state does not survive JSON round-trip"))

    # FOCUS: the focused selector must resolve.
    for msg in _check_focused_resolves(state):
        findings.append(Finding(_BC_FOCUS, msg))

    # INPUT_ROUTING: advertised selectors and available_actions must all resolve.
    for msg in _check_all_selectors_resolve(state):
        findings.append(Finding(_BC_INPUT_ROUTING, msg))
    for msg in _check_available_actions_resolve(state, mirror):
        findings.append(Finding(_BC_INPUT_ROUTING, msg))

    # RENDER: visible panel item labels and conversation lines must appear in renders.
    for msg in _check_labels_in_renders(state, ansi, markdown):
        findings.append(Finding(_BC_RENDER, msg))
    for line in state.conversation:
        text = line.render()
        if text not in ansi:
            findings.append(
                Finding(_BC_RENDER, f"Conversation text {text!r} missing from ANSI render")
            )
        if text not in markdown:
            findings.append(
                Finding(_BC_RENDER, f"Conversation text {text!r} missing from markdown render")
            )

    # LAYOUT: detect duplicate panel ids or popup ids (report each dup id once).
    panel_id_counts: dict[str, int] = {}
    for p in state.panels:
        panel_id_counts[p.id] = panel_id_counts.get(p.id, 0) + 1
    for pid, count in panel_id_counts.items():
        if count > 1:
            findings.append(Finding(_BC_LAYOUT, f"Duplicate panel id {pid!r}"))

    popup_id_counts: dict[str, int] = {}
    for p in state.popups:
        popup_id_counts[p.id] = popup_id_counts.get(p.id, 0) + 1
    for pid, count in popup_id_counts.items():
        if count > 1:
            findings.append(Finding(_BC_LAYOUT, f"Duplicate popup id {pid!r}"))

    # THEME: background coherence.
    if state.background.semantic and not state.background.theme:
        findings.append(Finding(_BC_THEME, "background.semantic set without a theme"))
    if state.background.frame < 0:
        findings.append(Finding(_BC_THEME, "background.frame is negative"))

    # POPUP_LIFECYCLE: every blocking popup must be visible.
    for popup in state.popups:
        if popup.blocking and not popup.visible:
            findings.append(
                Finding(_BC_POPUP_LIFECYCLE, f"blocking popup {popup.id!r} is not visible")
            )

    return Diagnosis(findings=findings)
