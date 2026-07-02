"""Tests for ``agentfront.testing.agreement`` — the cross-surface agreement assertion.

``assert_surfaces_agree`` wraps ``agentfront.serve.surface_inventory`` and turns
a set-disagreement between surfaces into a descriptive ``AssertionError`` — the
proof a consumer's own test suite runs to guarantee its CLI/MCP/HTTP/TAUI
surfaces never drift apart.
"""

from __future__ import annotations

import pytest

import agentfront.serve as serve
from agentfront import App
from agentfront.testing import assert_surfaces_agree

# --- fixtures ---------------------------------------------------------------


def _app() -> App:
    """A small example app with tools + docs, mirroring test_cli_surface.py."""
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


# --- passing case -------------------------------------------------------------


def test_assert_surfaces_agree_passes_on_normal_app() -> None:
    assert assert_surfaces_agree(_app()) is None


# --- disagreement: tools -------------------------------------------------------


def test_assert_surfaces_agree_raises_on_missing_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    real_inventory = serve.surface_inventory(app)

    def _fake_inventory(_app: App) -> dict[str, set[str]]:
        broken = dict(real_inventory)
        broken["cli_tools"] = set(real_inventory["cli_tools"]) - {"echo"}
        return broken

    monkeypatch.setattr(serve, "surface_inventory", _fake_inventory)

    with pytest.raises(AssertionError) as excinfo:
        assert_surfaces_agree(app)

    message = str(excinfo.value)
    assert "cli_tools" in message
    assert "registry_tools" in message
    assert "echo" in message


def test_assert_surfaces_agree_raises_on_extra_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    real_inventory = serve.surface_inventory(app)

    def _fake_inventory(_app: App) -> dict[str, set[str]]:
        broken = dict(real_inventory)
        broken["mcp_tools"] = set(real_inventory["mcp_tools"]) | {"ghost/tool"}
        return broken

    monkeypatch.setattr(serve, "surface_inventory", _fake_inventory)

    with pytest.raises(AssertionError) as excinfo:
        assert_surfaces_agree(app)

    message = str(excinfo.value)
    assert "mcp_tools" in message
    assert "registry_tools" in message
    assert "ghost/tool" in message


# --- disagreement: docs ---------------------------------------------------------


def test_assert_surfaces_agree_raises_on_doc_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    real_inventory = serve.surface_inventory(app)

    def _fake_inventory(_app: App) -> dict[str, set[str]]:
        broken = dict(real_inventory)
        broken["http_docs"] = set(real_inventory["http_docs"]) - {"intro"}
        return broken

    monkeypatch.setattr(serve, "surface_inventory", _fake_inventory)

    with pytest.raises(AssertionError) as excinfo:
        assert_surfaces_agree(app)

    message = str(excinfo.value)
    assert "http_docs" in message
    assert "registry_docs" in message
    assert "intro" in message


def test_assert_surfaces_agree_message_names_the_pair_not_just_a_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The message format follows the contract example:
    "cli_tools missing vs registry_tools: {'a/b'}".
    """
    app = _app()
    real_inventory = serve.surface_inventory(app)

    def _fake_inventory(_app: App) -> dict[str, set[str]]:
        broken = dict(real_inventory)
        broken["cli_tools"] = set(real_inventory["cli_tools"]) - {"echo"}
        return broken

    monkeypatch.setattr(serve, "surface_inventory", _fake_inventory)

    with pytest.raises(AssertionError) as excinfo:
        assert_surfaces_agree(app)

    message = str(excinfo.value)
    assert "missing" in message
    assert "vs" in message
