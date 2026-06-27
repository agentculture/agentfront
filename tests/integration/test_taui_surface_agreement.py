"""t12: TAUI surface agreement and dogfood gate.

The TAUI surface must enumerate the same tools as the registry, CLI, and MCP
surfaces.  The dogfood gate exercises the new taui build + diagnose path.
"""

from __future__ import annotations

from agentfront import App
from agentfront._dogfood import main as dogfood_main
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


def test_taui_tools_match_registry() -> None:
    """TAUI covers exactly the registry tools alongside cli/mcp."""
    app = _consumer_app()
    inv = surface_inventory(app)
    assert inv["taui_tools"] == inv["registry_tools"]


def test_surfaces_agree_includes_taui() -> None:
    """surfaces_agree is True when TAUI covers the registry tools."""
    assert surfaces_agree(_consumer_app()) is True


def test_dogfood_main_gate_passes() -> None:
    """The dogfood gate passes end-to-end for agentfront's own App."""
    assert dogfood_main() == 0
