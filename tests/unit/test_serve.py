"""Tests for the three-surface assembly + agreement check (t7).

Encodes t7's acceptance:
  - one App produces all three surfaces via one call each
  - the three surfaces AGREE: CLI learn == MCP tools == HTTP sitemap == registry
"""

from agentfront import App
from agentfront.serve import build_surfaces, surface_inventory, surfaces_agree


def _app() -> App:
    app = App(name="demo", version="1.0")
    app.add_doc(slug="intro", title="Intro", text="# Intro\nhi")
    app.add_doc(slug="guide/start", title="Start", text="# Start")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    @app.tool(name="echo", description="Echo")
    def echo(text: str) -> str:
        return text

    return app


def test_one_call_each_produces_all_three_surfaces():
    app = _app()
    surfaces = build_surfaces(app)
    assert surfaces.http is not None
    assert surfaces.mcp is not None
    assert surfaces.cli is not None
    # the App also exposes them directly, one call each
    assert app.http_app() is not None
    assert app.mcp_server() is not None
    assert app.cli() is not None


def test_surface_inventory_matches_registry():
    app = _app()
    inv = surface_inventory(app)
    assert inv["registry_docs"] == {"intro", "guide/start"}
    assert inv["registry_tools"] == {"search", "echo"}
    # every surface enumerates exactly the registry set
    assert inv["http_docs"] == inv["registry_docs"]
    assert inv["cli_docs"] == inv["registry_docs"]
    assert inv["cli_tools"] == inv["registry_tools"]
    assert inv["mcp_tools"] == inv["registry_tools"]


def test_surfaces_agree_on_a_normal_app():
    assert surfaces_agree(_app()) is True


def test_surfaces_agree_after_removal():
    # removing from the single registry must drop the item from EVERY surface,
    # so the surfaces still agree (no surface keeps a stale copy)
    app = _app()
    app.remove_doc("intro")
    app.remove_tool("echo")
    inv = surface_inventory(app)
    assert inv["http_docs"] == {"guide/start"}
    assert inv["mcp_tools"] == {"search"}
    assert inv["cli_docs"] == {"guide/start"}
    assert surfaces_agree(app) is True


def test_empty_app_surfaces_agree():
    app = App(name="empty")
    inv = surface_inventory(app)
    assert inv["http_docs"] == set()
    assert inv["mcp_tools"] == set()
    assert surfaces_agree(app) is True
