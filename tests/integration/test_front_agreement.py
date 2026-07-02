"""Agreement gate extended to the HTTP ``/front`` markdown tier (t8).

``surfaces_agree`` already proved the CLI/MCP/HTTP/TAUI *inventories* line up.
This closes the last gap: the HTTP ``/front`` route must serve the exact same
bytes as the TAUI markdown tier (``render_markdown(app.taui())``) — not just a
route that returns *some* markdown. ``http_front_agrees`` makes that check
independently callable; ``surfaces_agree`` folds it in.
"""

from __future__ import annotations

from agentfront import App
from agentfront.serve import http_front_agrees, surface_inventory, surfaces_agree
from agentfront.taui.render.markdown import render_markdown


def _app() -> App:
    app = App(name="demo", version="1.0", description="A demo tool")
    app.add_doc(slug="intro", title="Intro", text="# Intro\nhi")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    return app


# --- http_front_agrees -------------------------------------------------


def test_http_front_agrees_true_for_a_real_app() -> None:
    app = _app()
    assert http_front_agrees(app) is True


def test_http_front_agrees_matches_render_markdown_of_app_taui() -> None:
    app = _app()
    # Confirm the equality basis directly, not just the boolean.
    assert http_front_agrees(app) is True
    wsgi = app.http_app()
    body = b"".join(wsgi({"REQUEST_METHOD": "GET", "PATH_INFO": "/front"}, lambda *a: None))
    assert body.decode("utf-8") == render_markdown(app.taui())


def test_http_front_agrees_is_in_all() -> None:
    from agentfront import serve

    assert "http_front_agrees" in serve.__all__


# --- surfaces_agree folds the front check in ----------------------------


def test_surfaces_agree_true_for_a_real_app_including_front() -> None:
    assert surfaces_agree(_app()) is True


def test_broken_front_is_detected_by_surfaces_agree(monkeypatch) -> None:
    """A /front route that drifts from the TAUI markdown tier must flip
    ``surfaces_agree`` to False, even though docs/tools still agree."""
    import agentfront.http_surface as http_surface

    app = _app()

    def _broken_front(app):
        return (
            "200 OK",
            [("Content-Type", "text/markdown; charset=utf-8")],
            b"# This is not the TAUI markdown tier\n",
        )

    monkeypatch.setattr(http_surface, "_front", _broken_front)

    # docs/tools inventories are untouched by the broken /front route.
    inv = surface_inventory(app)
    docs_agree = inv["registry_docs"] == inv["http_docs"] == inv["cli_docs"]
    tools_agree = inv["registry_tools"] == inv["cli_tools"] == inv["mcp_tools"] == inv["taui_tools"]
    assert docs_agree is True
    assert tools_agree is True

    assert http_front_agrees(app) is False
    assert surfaces_agree(app) is False


def test_broken_front_via_render_markdown_monkeypatch(monkeypatch) -> None:
    """Same detection, breaking the HTTP side only by patching the render
    function the ``/front`` handler resolves at call time."""
    import agentfront.taui.render.markdown as md

    app = _app()
    real_render_markdown = md.render_markdown
    calls = {"n": 0}

    def _flaky_render_markdown(state):
        # The /front handler is the FIRST caller in http_front_agrees'
        # sequence (it builds the WSGI body before computing the expected
        # value), so returning a different string only on the first call
        # breaks just the HTTP side of the comparison.
        calls["n"] += 1
        if calls["n"] == 1:
            return "# drifted\n"
        return real_render_markdown(state)

    monkeypatch.setattr(md, "render_markdown", _flaky_render_markdown)
    assert http_front_agrees(app) is False
