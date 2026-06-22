"""Unit tests for agentfront.http_surface — the WSGI HTTP surface (t1).

Drive ``make_http_app`` via ``wsgiref.test.create_environ`` and a captured
``start_response`` — no real socket needed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405
from typing import Any

from agentfront import App
from agentfront.http_surface import make_http_app


def _environ(path: str) -> dict[str, Any]:
    """Build a minimal WSGI environ for a GET request."""
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
    }


def _call_app(app: App, path: str) -> tuple[str, list[bytes]]:
    """Invoke the WSGI app and return (status, body_chunks)."""
    environ = _environ(path)
    captured_status: list[str] = []
    captured_headers: list[tuple[str, str]] = []

    def _start_response(status: str, headers: list[tuple[str, str]]):
        captured_status.append(status)
        captured_headers.extend(headers)
        return lambda b: None

    wsgi_app = make_http_app(app)
    body = list(wsgi_app(environ, _start_response))
    return captured_status[0], body, captured_headers


def _body_text(status, body, headers) -> str:
    return b"".join(body).decode("utf-8")


# --- doc route -----------------------------------------------------------


def test_registered_doc_fetchable():
    app = App(name="t")
    app.add_doc(slug="guide/intro", title="Intro", text="# Hello\nworld")
    status, body, headers = _call_app(app, "/guide/intro")
    assert status.startswith("200")
    assert _body_text(status, body, headers) == "# Hello\nworld"


def test_doc_content_type_is_markdown():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="x")
    _, _, headers = _call_app(app, "/a")
    ct = dict(headers).get("Content-Type", "")
    assert "text/markdown" in ct


def test_unknown_slug_returns_404():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="x")
    status, body, _ = _call_app(app, "/nope")
    assert status.startswith("404")


# --- index route ---------------------------------------------------------


def test_index_lists_all_slugs():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="a")
    app.add_doc(slug="b", title="B", text="b")
    status, body, _ = _call_app(app, "/")
    assert status.startswith("200")
    text = _body_text(status, body, _)
    assert "/a" in text
    assert "/b" in text


# --- sitemap ----------------------------------------------------------------


def test_sitemap_xml_parses():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="a")
    app.add_doc(slug="b", title="B", text="b")
    status, body, headers = _call_app(app, "/sitemap.xml")
    assert status.startswith("200")
    ct = dict(headers).get("Content-Type", "")
    assert "application/xml" in ct
    tree = ET.fromstring(b"".join(body))  # noqa: S314
    locs = [el.text for el in tree.iter("loc")]
    assert sorted(locs) == ["/a", "/b"]


def test_sitemap_lists_exactly_registered_slugs():
    app = App(name="t")
    app.add_doc(slug="guide/intro", title="Intro", text="x")
    status, body, _ = _call_app(app, "/sitemap.xml")
    tree = ET.fromstring(b"".join(body))  # noqa: S314
    locs = [el.text for el in tree.iter("loc")]
    assert locs == ["/guide/intro"]


# --- no HTML / no JS / no CSS -------------------------------------------


def test_doc_response_has_no_html_tags():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="x")
    status, body, _ = _call_app(app, "/a")
    text = _body_text(status, body, _).lower()
    assert "<html>" not in text
    assert "<script>" not in text
    assert "<style>" not in text


def test_sitemap_response_has_no_html_tags():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="x")
    status, body, _ = _call_app(app, "/sitemap.xml")
    text = _body_text(status, body, _).lower()
    assert "<html>" not in text
    assert "<script>" not in text
    assert "<style>" not in text


def test_index_response_has_no_html_tags():
    app = App(name="t")
    app.add_doc(slug="a", title="A", text="x")
    status, body, _ = _call_app(app, "/")
    text = _body_text(status, body, _).lower()
    assert "<html>" not in text
    assert "<script>" not in text
    assert "<style>" not in text
