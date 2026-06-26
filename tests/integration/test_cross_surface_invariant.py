"""t11: cross-surface invariant under single-dispatch MCP.

From ONE registry: the CLI verb set, the single MCP ``run`` tool's command
catalog, and the ``learn`` catalog all enumerate the same operations, the HTTP
surface still serves the registry docs, and adding/removing an op propagates to
all three surfaces together.

Covers plan targets c23 / c37 / h23 / h25 / h27.
"""

from __future__ import annotations

from agentfront import App
from agentfront.serve import surface_inventory, surfaces_agree


def _consumer_app() -> App:
    app = App(name="demo", version="1.0")
    app.add_doc(slug="guide", title="Guide", text="# Guide\nhello")
    fb = app.group("feedback")

    @fb.tool
    def record(item: str) -> str:
        "Record a feedback item."
        return item

    @fb.tool
    def show(ident: str) -> str:
        "Show one feedback item."
        return ident

    @app.tool
    def search(query: str) -> str:
        "Search the corpus."
        return query

    return app


def test_surfaces_agree_under_single_dispatch() -> None:
    # h25: surfaces_agree is True for a consumer App under single-dispatch MCP.
    assert surfaces_agree(_consumer_app()) is True


def test_cli_mcp_learn_enumerate_same_set() -> None:
    # h23/c23: CLI verb set == single MCP tool's command catalog == learn catalog.
    inv = surface_inventory(_consumer_app())
    assert inv["registry_tools"] == inv["cli_tools"] == inv["mcp_tools"]
    assert inv["mcp_tools"] == {"feedback/record", "feedback/show", "search"}


def test_http_surface_still_serves_registry_docs() -> None:
    # c23: http_app() still serves the registry docs.
    inv = surface_inventory(_consumer_app())
    assert inv["registry_docs"] == inv["http_docs"] == inv["cli_docs"]
    assert "guide" in inv["http_docs"]


def test_add_op_appears_in_all_three_surfaces() -> None:
    # h27: adding an op makes it appear in CLI, MCP catalog, and learn together,
    # with no hand-edited catalog.
    app = _consumer_app()

    @app.group("feedback").tool
    def archive(ident: str) -> str:
        "Archive a feedback item."
        return ident

    inv = surface_inventory(app)
    for surface in ("registry_tools", "cli_tools", "mcp_tools"):
        assert "feedback/archive" in inv[surface], surface
    assert surfaces_agree(app) is True


def test_remove_op_disappears_from_all_three_surfaces() -> None:
    app = _consumer_app()
    app.remove_tool(("feedback", "record"))
    inv = surface_inventory(app)
    for surface in ("registry_tools", "cli_tools", "mcp_tools"):
        assert "feedback/record" not in inv[surface], surface
    assert surfaces_agree(app) is True
