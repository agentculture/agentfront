"""Story drift gate — docs/how-it-works.md must not drift from the real shape.

``docs/how-it-works.md`` is the canonical "how agentfront works" narrative:
one ``App`` renders every surface, and each rendering/surface maps to a
named consumer in a table. This test is the drift gate for that table — it
reads the *live* :class:`agentfront.serve.Surfaces` dataclass (rather than a
hardcoded list) so a future rename/add/remove of a surface field fails this
test until the doc is updated to match, instead of silently going stale.

It also locks the three TAUI rendering-tier names (JSON, Markdown, ANSI)
that the doc's table is required to name individually.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from agentfront import App
from agentfront.serve import build_surfaces

_DOC_PATH = Path(__file__).parents[2] / "docs" / "how-it-works.md"

# The three TAUI render tiers (agentfront/taui/render/{ansi,markdown}.py and
# the JSON mirror in agentfront/taui/mirror.py) — locked by name here.
_TAUI_RENDERING_NAMES = ("JSON", "Markdown", "ANSI")


def _tiny_app() -> App:
    """A minimal App — just enough to build a real Surfaces instance from."""
    app = App(name="story-drift", version="1.0.0", description="tiny app for the drift gate")
    app.add_doc(slug="intro", title="Intro", text="# Intro\nhello")

    @app.tool
    def ping() -> str:
        """Ping the tiny app."""
        return "pong"

    return app


def _table_section(doc_text: str) -> str:
    """The markdown table row lines in *doc_text* (GFM pipe-table rows).

    docs/how-it-works.md is expected to hold its rendering/surface -> consumer
    mapping in a single markdown table; this pulls out every ``|``-prefixed
    line across the doc so the assertions below are scoped to table content
    rather than incidental prose mentions.
    """
    return "\n".join(line for line in doc_text.splitlines() if line.strip().startswith("|"))


def test_how_it_works_doc_exists() -> None:
    assert _DOC_PATH.is_file(), f"canonical story doc missing: {_DOC_PATH}"


def test_doc_table_names_every_surfaces_field() -> None:
    """Every field name on the live Surfaces dataclass must appear in the table."""
    surfaces = build_surfaces(_tiny_app())
    field_names = [f.name for f in dataclasses.fields(surfaces)]
    assert field_names, "Surfaces has no fields — nothing to check the doc against"

    table = _table_section(_DOC_PATH.read_text(encoding="utf-8"))
    missing = [name for name in field_names if name not in table]
    assert not missing, (
        f"docs/how-it-works.md table is missing Surfaces field(s) {missing} "
        f"(live fields: {field_names})"
    )


def test_doc_table_names_every_taui_rendering() -> None:
    """The three TAUI rendering-tier names must appear in the table."""
    table = _table_section(_DOC_PATH.read_text(encoding="utf-8"))
    missing = [name for name in _TAUI_RENDERING_NAMES if name not in table]
    assert not missing, (
        f"docs/how-it-works.md table is missing TAUI rendering name(s) {missing} "
        f"(expected: {_TAUI_RENDERING_NAMES})"
    )
