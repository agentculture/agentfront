"""TAUI snapshot quad — write/read <stem>.taui.json/.ansi/.events.jsonl/.md + faithfulness.

``resume`` is the HANDOFF primitive built on top of the quad: an agent
pauses a live session with ``write_snapshot`` (or hands over an in-memory
``Snapshot`` directly), and a human — or another agent — picks it back up
with ``resume`` (typically feeding the result straight into a
:class:`~agentfront.taui.driver.LiveDriver`), or vice versa: a human pauses
and an agent resumes. Either audience can be on either end of the handoff;
nothing on the event trail is lost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentfront.taui.events import Event, dumps_events, loads_events
from agentfront.taui.mirror import serialize
from agentfront.taui.reducer import replay  # noqa: F401 — re-exported for callers
from agentfront.taui.render.ansi import render_ansi
from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.state import TAUIState

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle at runtime
    from agentfront.app import App
    from agentfront.taui.session import Session

# ---------------------------------------------------------------------------
# Module constants (SonarCloud S1192 — avoid repeated string literals).
# ---------------------------------------------------------------------------

_SUFFIX_JSON = ".taui.json"
_SUFFIX_ANSI = ".ansi"
_SUFFIX_EVENTS = ".events.jsonl"
_SUFFIX_MD = ".md"

_KEY_JSON = "json"
_KEY_ANSI = "ansi"
_KEY_EVENTS = "events"
_KEY_MD = "md"

_FIELD_PANELS = "panels"
_FIELD_VISIBLE = "visible"
_FIELD_ITEMS = "items"
_FIELD_LABEL = "label"
_FIELD_ID = "id"
_FIELD_CONVERSATION = "conversation"
_FIELD_TEXT = "text"
_FIELD_COUNT = "count"


# ---------------------------------------------------------------------------
# Snapshot dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Snapshot:
    """A point-in-time capture of a TAUIState with its renders and event trail."""

    state: TAUIState
    ansi: str
    markdown: str
    events: list[Event] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def snapshot_paths(stem: str | Path) -> dict[str, Path]:
    """Return the four file paths for a snapshot *stem*.

    Keys: ``"json"``, ``"ansi"``, ``"events"``, ``"md"``.
    Paths are formed by string-suffixing the stem — e.g., stem ``"foo"``
    yields ``"foo.taui.json"``, ``"foo.ansi"``, ``"foo.events.jsonl"``,
    ``"foo.md"``.
    """
    p = Path(stem)
    return {
        _KEY_JSON: Path(str(p) + _SUFFIX_JSON),
        _KEY_ANSI: Path(str(p) + _SUFFIX_ANSI),
        _KEY_EVENTS: Path(str(p) + _SUFFIX_EVENTS),
        _KEY_MD: Path(str(p) + _SUFFIX_MD),
    }


# ---------------------------------------------------------------------------
# Write / read
# ---------------------------------------------------------------------------


def write_snapshot(
    stem: str | Path,
    state: TAUIState,
    events: list[Event] | None = None,
) -> dict[str, Path]:
    """Write the four snapshot files for *state*.

    - ``<stem>.taui.json`` — ``json.dumps(serialize(state), indent=2)``
    - ``<stem>.ansi`` — ``render_ansi(state)``
    - ``<stem>.md`` — ``render_markdown(state)``
    - ``<stem>.events.jsonl`` — ``dumps_events(events or [])``

    Parent directories are created as needed. Returns the path dict from
    :func:`snapshot_paths`.
    """
    paths = snapshot_paths(stem)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    paths[_KEY_JSON].write_text(json.dumps(serialize(state), indent=2), encoding="utf-8")
    paths[_KEY_ANSI].write_text(render_ansi(state), encoding="utf-8")
    paths[_KEY_MD].write_text(render_markdown(state), encoding="utf-8")
    paths[_KEY_EVENTS].write_text(dumps_events(events or []), encoding="utf-8")

    return paths


def read_snapshot(stem: str | Path) -> Snapshot:
    """Read and reconstruct a :class:`Snapshot` from the four files at *stem*.

    ``state`` is reconstructed via ``TAUIState.from_dict(json.loads(...))``;
    extra mirror keys (``taui_version``, ``available_actions``) are silently
    ignored by ``from_dict``.  ``events`` defaults to ``[]`` when the
    ``.events.jsonl`` file is empty.
    """
    paths = snapshot_paths(stem)
    state = TAUIState.from_dict(json.loads(paths[_KEY_JSON].read_text(encoding="utf-8")))
    ansi = paths[_KEY_ANSI].read_text(encoding="utf-8")
    markdown = paths[_KEY_MD].read_text(encoding="utf-8")
    events_text = paths[_KEY_EVENTS].read_text(encoding="utf-8")
    events = loads_events(events_text)
    return Snapshot(state=state, ansi=ansi, markdown=markdown, events=events)


# ---------------------------------------------------------------------------
# resume — the handoff primitive
# ---------------------------------------------------------------------------


def resume(source: str | Path | Snapshot, app: App) -> Session:
    """Resume a live :class:`~agentfront.taui.session.Session` from a snapshot.

    This is the HANDOFF primitive: whoever paused the session (agent or
    human) captured it with :func:`write_snapshot`; whoever picks it back up
    (human or agent — either direction) calls ``resume`` to get a live
    ``Session`` continuing from exactly that point, then drives it onward
    (an agent via ``session.dispatch``/``session.fold``, a human typically
    via :class:`~agentfront.taui.driver.LiveDriver`). Nothing on the event
    trail is lost across the handoff.

    *source* is either a snapshot *stem* (resolved via :func:`read_snapshot`)
    or an already-loaded :class:`Snapshot` (no file I/O in that case — e.g.
    a snapshot handed over in-memory rather than serialized to disk).

    The returned session's ``state`` is the snapshotted state, its
    ``events`` are the snapshotted trail, its ``initial`` equals that same
    state, and its ``replay_base_index`` equals ``len(events)`` — the
    session provides these semantics (see
    :class:`agentfront.taui.session.Session`); this function does not
    reimplement them, it just supplies the constructor arguments.
    """
    # Lazy import: agentfront.taui.session imports agentfront.app.App, and
    # keeping that import out of this module's top level avoids a cycle
    # between snapshot.py and session.py.
    from agentfront.taui.session import Session as _Session

    snap = source if isinstance(source, Snapshot) else read_snapshot(source)
    return _Session(app, state=snap.state, events=list(snap.events))


# ---------------------------------------------------------------------------
# Faithfulness check
# ---------------------------------------------------------------------------


def faithful(mirror: dict[str, Any], markdown: str) -> list[str]:
    """Check JSON↔Markdown faithfulness.

    Every visible panel item label and every conversation line text present in
    *mirror* must appear in *markdown*.

    Returns a list of human-readable discrepancy strings; an empty list means
    the mirror and markdown are faithful to each other.
    """
    discrepancies: list[str] = []

    for panel in mirror.get(_FIELD_PANELS, []):
        if not panel.get(_FIELD_VISIBLE, True):
            continue
        for item in panel.get(_FIELD_ITEMS, []):
            label = item.get(_FIELD_LABEL, "")
            if label and label not in markdown:
                discrepancies.append(
                    f"panel item label {label!r} from panel"
                    f" {panel.get(_FIELD_ID, '?')!r} not found in markdown"
                )

    for conv in mirror.get(_FIELD_CONVERSATION, []):
        text = conv.get(_FIELD_TEXT, "")
        count = conv.get(_FIELD_COUNT, 1)
        # Look for the RENDERED form ("text ×N" when collapsed), matching what
        # the renderers emit and what diagnose_structured's RENDER check expects.
        rendered = text if count <= 1 else f"{text} ×{count}"
        if rendered and rendered not in markdown:
            discrepancies.append(f"conversation line {rendered!r} not found in markdown")

    return discrepancies
