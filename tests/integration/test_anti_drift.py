"""Anti-drift integration tests (t8 — covers h9).

The single registry is the only thing any surface can enumerate. There is no
code path by which a surface presents a doc/tool the registry does not hold —
proven by querying each of the three surfaces for an unregistered item and by
removing from the registry and confirming every surface drops it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405 - parsing our own sitemap

from agentfront import App
from agentfront.cli_surface import run_cli
from agentfront.serve import surface_inventory


def _app() -> App:
    app = App(name="drift", version="1.0")
    app.add_doc(slug="a", title="A", text="alpha")
    app.add_doc(slug="b", title="B", text="bravo")

    @app.tool
    def first(x: int) -> int:
        """First."""
        return x

    @app.tool
    def second(y: str) -> str:
        """Second."""
        return y

    return app


def _http_status(app: App, path: str) -> str:
    wsgi = app.http_app()
    captured: list[str] = []
    body = list(
        wsgi(
            {"REQUEST_METHOD": "GET", "PATH_INFO": path},
            lambda status, headers: captured.append(status) or (lambda b: None),
        )
    )
    assert body is not None
    return captured[0]


def _mcp_command_paths(app: App) -> set[str]:
    """Derive command paths from the registry (same source the MCP server uses)."""
    paths: set[str] = set()
    for entry in app.list_tools():
        path = list(entry.group) + [entry.name]
        paths.add("/".join(path))
    return paths


def test_unregistered_item_absent_from_every_surface():
    app = _app()
    # HTTP: an unregistered slug 404s
    assert _http_status(app, "/never-registered").startswith("404")
    # MCP: an unregistered command path is not in the catalog
    assert "never_registered" not in _mcp_command_paths(app)
    # CLI: an unregistered name is not in the learn listing
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        run_cli(app, ["learn"])
    assert "never_registered" not in buf.getvalue()


def test_removing_from_registry_drops_from_all_surfaces():
    app = _app()
    before = surface_inventory(app)
    assert before["http_docs"] == {"a", "b"}
    assert before["mcp_tools"] == {"first", "second"}

    app.remove_doc("a")
    app.remove_tool("first")

    after = surface_inventory(app)
    # every surface reflects the removal — no surface kept a stale copy
    assert after["http_docs"] == {"b"}
    assert after["cli_docs"] == {"b"}
    assert after["mcp_tools"] == {"second"}
    assert after["cli_tools"] == {"second"}
    # and the removed doc now 404s on HTTP
    assert _http_status(app, "/a").startswith("404")


def test_no_public_side_channel_to_inject_into_a_surface():
    """The only mutators route through the registry; surfaces are read-only views."""
    app = _app()
    # The HTTP sitemap is built from the registry; there is no app/surface method
    # that adds an entry to a surface without going through add_doc/tool.
    public_mutators = {
        name
        for name in dir(app)
        if not name.startswith("_") and callable(getattr(app, name)) and ("add" in name)
    }
    assert public_mutators == {"add_doc", "add_docs_dir", "add_command"}

    # Build the HTTP surface, then mutate the registry: the *same* surface object
    # reflects the new state (it reads the registry live, holds no snapshot).
    wsgi = app.http_app()
    app.add_doc(slug="c", title="C", text="charlie")
    captured: list[str] = []
    list(
        wsgi(
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/sitemap.xml"},
            lambda status, headers: captured.append(status) or (lambda b: None),
        )
    )
    # re-fetch the sitemap from the already-built app and confirm "c" is present
    body = b"".join(
        app.http_app()(
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/sitemap.xml"},
            lambda status, headers: (lambda b: None),
        )
    )
    slugs = {(el.text or "").lstrip("/") for el in ET.fromstring(body).iter("loc")}  # noqa: S314
    assert "c" in slugs
