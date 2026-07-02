"""Unit tests for the HTTP ``/front`` route (t4).

``/front`` serves the SAME TAUI markdown tier used by the snapshot/render
pipeline — ``render_markdown(make_baseline(app))`` — over HTTP, so any agent
with a fetch tool gets the live-cockpit view without a bespoke client.

Drive ``make_http_app`` directly with a WSGI environ dict (no real socket),
matching the technique in ``agentfront.serve._http_doc_slugs`` and the
existing ``tests/unit/test_http_surface.py``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405
from typing import Any

import pytest

from agentfront import App
from agentfront.http_surface import make_http_app
from agentfront.taui.derive import make_baseline
from agentfront.taui.render.markdown import render_markdown


def _environ(path: str) -> dict[str, Any]:
    """Build a minimal WSGI environ for a GET request."""
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
    }


def _call_app(app: App, path: str) -> tuple[str, list[bytes], list[tuple[str, str]]]:
    """Invoke the WSGI app and return (status, body_chunks, headers)."""
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


def _body_text(body: list[bytes]) -> str:
    return b"".join(body).decode("utf-8")


@pytest.fixture
def app() -> App:
    """A small App with a couple of tools + docs, mirroring other surface tests."""
    a = App(name="mytool", version="1.0.0", description="A test tool")
    a.add_doc(slug="intro", title="Introduction", text="# Intro\nbody")
    a.add_doc(slug="usage", title="Usage Guide", text="# Usage\nhow to")

    @a.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    @a.tool(name="index")
    def _index(path: str) -> str:
        """Index a file."""
        return path

    return a


# --- /front route ----------------------------------------------------------


def test_front_returns_200(app: App) -> None:
    status, _, _ = _call_app(app, "/front")
    assert status.startswith("200")


def test_front_content_type_is_markdown(app: App) -> None:
    _, _, headers = _call_app(app, "/front")
    ct = dict(headers).get("Content-Type", "")
    assert ct == "text/markdown; charset=utf-8"


def test_front_body_matches_taui_markdown_tier(app: App) -> None:
    """/front body == the SAME code path as the TAUI markdown tier."""
    _, body, _ = _call_app(app, "/front")
    expected = render_markdown(make_baseline(app))
    assert _body_text(body) == expected


def test_front_body_matches_app_taui(app: App) -> None:
    """Also matches render_markdown(app.taui()) — App's own accessor."""
    _, body, _ = _call_app(app, "/front")
    expected = render_markdown(app.taui())
    assert _body_text(body) == expected


# --- links from other surfaces ----------------------------------------------


def test_index_links_to_front(app: App) -> None:
    status, body, _ = _call_app(app, "/")
    assert status.startswith("200")
    assert "/front" in _body_text(body)


def test_llms_txt_links_to_front(app: App) -> None:
    status, body, _ = _call_app(app, "/llms.txt")
    assert status.startswith("200")
    text = _body_text(body)
    assert "/front" in text
    assert "Front" in text


# --- agreement gate: sitemap stays docs-only --------------------------------


def test_sitemap_does_not_contain_front(app: App) -> None:
    """The cross-surface agreement gate parses the sitemap as docs-only —
    /front must never appear there."""
    status, body, _ = _call_app(app, "/sitemap.xml")
    assert status.startswith("200")
    tree = ET.fromstring(b"".join(body))  # noqa: S314
    locs = {el.text for el in tree.iter("loc")}
    assert "/front" not in locs


# --- existing routes unchanged ----------------------------------------------


def test_unknown_path_still_404(app: App) -> None:
    status, _, _ = _call_app(app, "/does-not-exist")
    assert status.startswith("404")
