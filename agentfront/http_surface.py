"""HTTP surface for agentfront — a WSGI app serving docs as markdown.

Builds a navigable markdown site from an :class:`App`'s registry. Uses only
the Python standard library (``wsgiref`` / ``xml.etree``). No third-party
dependencies.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET  # noqa: S405
from http.server import HTTPServer
from typing import Any
from wsgiref.simple_server import make_server

from agentfront.app import App

__all__ = ["make_http_app", "serve"]

# Status lines and content types, named once so the routes below read from a
# single source instead of repeating the literals (SonarCloud S1192).
_STATUS_OK = "200 OK"
_STATUS_NOT_FOUND = "404 Not Found"
_CT_MARKDOWN = "text/markdown; charset=utf-8"
_CT_PLAIN = "text/plain; charset=utf-8"
_CT_XML = "application/xml"


def make_http_app(app: App) -> Any:
    """Return a WSGI application callable built from *app*.

    Routes:
      - ``GET /<slug>`` → doc body (``text/markdown``), 404 if unknown.
      - ``GET /sitemap.xml`` → XML ``<urlset>`` with one ``<url>`` per doc.
      - ``GET /`` → markdown index linking to each ``/<slug>``.
      - ``GET /front`` → the TAUI markdown tier for this App (same code path
        as the snapshot/render pipeline). Intentionally NOT a doc: it is not
        listed in ``/sitemap.xml``, which the cross-surface agreement gate
        parses as docs-only.
    """

    def application(environ: dict[str, Any], start_response: Any) -> list[bytes]:
        path = environ.get("PATH_INFO", "/")

        if path == "/sitemap.xml":
            status, headers, body = _sitemap(app)
        elif path == "/llms.txt":
            status, headers, body = _llms_txt(app)
        elif path == "/front":
            status, headers, body = _front(app)
        elif path == "/":
            status, headers, body = _index(app)
        else:
            status, headers, body = _doc(app, path)

        start_response(status, headers)
        return [body]

    return application


def _doc(app: App, path: str) -> tuple[str, list[tuple[str, str]], bytes]:
    """Serve a single doc by slug (path without leading ``/``)."""
    slug = path.lstrip("/")
    entry = app.get_doc(slug)
    if entry is None:
        return (
            _STATUS_NOT_FOUND,
            [("Content-Type", _CT_PLAIN)],
            b"Not found",
        )
    body = entry.text.encode("utf-8")
    return (
        _STATUS_OK,
        [("Content-Type", _CT_MARKDOWN)],
        body,
    )


def _index(app: App) -> tuple[str, list[tuple[str, str]], bytes]:
    """Render a markdown index page linking to every registered doc."""
    lines: list[str] = ["# Documentation"]
    for entry in app.list_docs():
        lines.append(f"- [{entry.title}](/{entry.slug})")
    lines.append("- [Front](/front)")
    body = "\n".join(lines) + "\n"
    return (
        _STATUS_OK,
        [("Content-Type", _CT_MARKDOWN)],
        body.encode("utf-8"),
    )


def _front(app: App) -> tuple[str, list[tuple[str, str]], bytes]:
    """Render the TAUI markdown tier for *app* — the ``/front`` view.

    Lazy imports keep this module's import light: the TAUI render/derive
    stack is only pulled in when ``/front`` is actually requested. This is
    the SAME code path as the TAUI markdown tier (snapshot/render pipeline)
    — no parallel renderer.
    """
    from agentfront.taui.derive import make_baseline
    from agentfront.taui.render.markdown import render_markdown

    body = render_markdown(make_baseline(app)).encode("utf-8")
    return (
        _STATUS_OK,
        [("Content-Type", _CT_MARKDOWN)],
        body,
    )


def _llms_txt(app: App) -> tuple[str, list[tuple[str, str]], bytes]:
    """Render an ``/llms.txt`` discovery file (the agent-first entry point).

    A single fetch tells an agent the tool's name, its docs (as links), and its
    tool menu — both surfaces' contents from one well-known URL.
    """
    lines: list[str] = [f"# {app.name}"]
    if app.description:
        lines += ["", f"> {app.description}"]
    lines += ["", "## Docs"]
    for entry in app.list_docs():
        lines.append(f"- [{entry.title}](/{entry.slug})")
    lines += ["", "## Tools"]
    for tool in app.list_tools():
        lines.append(f"- {tool.name}: {tool.description}")
    lines += ["", "## Front", "- [Front](/front) — the live-cockpit view as markdown"]
    body = "\n".join(lines) + "\n"
    return (
        _STATUS_OK,
        [("Content-Type", _CT_MARKDOWN)],
        body.encode("utf-8"),
    )


def _sitemap(app: App) -> tuple[str, list[tuple[str, str]], bytes]:
    """Render a well-formed XML sitemap."""
    urlset = ET.Element("urlset")
    for entry in app.list_docs():
        url = ET.SubElement(urlset, "url")
        loc = ET.SubElement(url, "loc")
        loc.text = f"/{entry.slug}"
    tree = ET.ElementTree(urlset)
    buf = io.BytesIO()
    tree.write(buf, xml_declaration=True, encoding="utf-8")
    return (
        _STATUS_OK,
        [("Content-Type", _CT_XML)],
        buf.getvalue(),
    )


def serve(app: App, host: str = "127.0.0.1", port: int = 0) -> HTTPServer:
    """Start an HTTP server serving *app* (blocking call).

    Returns the :class:`HTTPServer` instance so the caller can shut it down.
    """
    wsgi_app = make_http_app(app)
    server = make_server(host, port, wsgi_app)
    return server
