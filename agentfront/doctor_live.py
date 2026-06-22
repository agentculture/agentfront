"""Runtime doctor — audits an App's live surfaces and returns findings.

Builds each surface (HTTP, CLI) and probes it in-process. Returns a list of
:class:`Check` results; warnings are allowed, only ``"fail"`` makes the app
unhealthy.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405
from dataclasses import dataclass
from typing import Any

from agentfront.app import App
from agentfront.cli_surface import run_cli
from agentfront.http_surface import make_http_app

__all__ = ["Check", "run_doctor", "healthy"]

THRESHOLD = 12


@dataclass(frozen=True)
class Check:
    """Result of a single doctor check."""

    name: str
    status: str  # "ok" | "warn" | "fail"
    remediation: str


def _wsgi_get(wsgi_app: Any, environ: dict[str, Any]) -> tuple[str, list[bytes]]:
    """Invoke a WSGI app and return (status_line, body_chunks)."""

    captured_status: list[str] = []
    captured_body: list[bytes] = []

    def _start_response(status: str, _headers: list[tuple[str, str]]) -> Any:
        captured_status.append(status)
        return lambda b: captured_body.append(b)

    body = list(wsgi_app(environ, _start_response))
    return captured_status[0], body


def _check_sitemap(app: App) -> Check:
    """Verify GET /sitemap.xml returns 200 and lists registered doc slugs."""
    wsgi = make_http_app(app)
    environ: dict[str, Any] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/sitemap.xml",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8000",
        "wsgi.url_scheme": "http",
    }

    status, body = _wsgi_get(wsgi, environ)
    body_raw = b"".join(body)

    if not status.startswith("200"):
        return Check(
            name="sitemap",
            status="fail",
            remediation="GET /sitemap.xml did not return 200; check the HTTP surface.",
        )

    try:
        tree = ET.fromstring(body_raw)  # noqa: S314
    except ET.ParseError:
        return Check(
            name="sitemap",
            status="fail",
            remediation="sitemap.xml is not valid XML; check the HTTP surface.",
        )

    locs = sorted(el.text for el in tree.iter("loc"))
    expected = sorted(f"/{d.slug}" for d in app.list_docs())

    if locs == expected and locs:
        return Check(name="sitemap", status="ok", remediation="")

    return Check(
        name="sitemap",
        status="fail",
        remediation=(
            f"sitemap lists {len(locs)} locations but app has {len(expected)} docs; "
            "ensure all docs are registered before building the HTTP surface."
        ),
    )


def _check_mcp_menu_size(app: App) -> Check:
    """Warn when the tool menu exceeds THRESHOLD."""
    count = len(app.list_tools())
    if count <= THRESHOLD:
        return Check(name="mcp_menu_size", status="ok", remediation="")

    return Check(
        name="mcp_menu_size",
        status="warn",
        remediation=(
            f"Tool menu has {count} entries (threshold {THRESHOLD}); "
            "curate or collapse the menu to improve agent readability."
        ),
    )


def _check_learn(app: App) -> Check:
    """Verify the CLI exposes a ``learn`` subcommand that exits 0."""
    try:
        rc = run_cli(app, ["learn"])
    except Exception:
        return Check(
            name="learn",
            status="fail",
            remediation="run_cli(app, ['learn']) raised an exception; check the CLI surface.",
        )

    if rc == 0:
        return Check(name="learn", status="ok", remediation="")

    return Check(
        name="learn",
        status="fail",
        remediation="run_cli(app, ['learn']) exited non-zero; check the CLI surface.",
    )


def run_doctor(app: App) -> list[Check]:
    """Audit *app*'s live surfaces and return findings."""
    return [
        _check_sitemap(app),
        _check_mcp_menu_size(app),
        _check_learn(app),
    ]


def healthy(checks: list[Check]) -> bool:
    """Return ``True`` when no check has status ``"fail"``."""
    return not any(c.status == "fail" for c in checks)
