"""Tests for ``agentfront.cli_surface`` — the host-agnostic CLI surface.

The host writes ZERO argparse code; ``make_cli(app)`` / ``run_cli(app, argv)``
build the CLI from the App's registry.
"""

from __future__ import annotations

import json

import pytest

from agentfront import App
from agentfront.cli_surface import make_cli, run_cli

# --- fixtures -----------------------------------------------------------


@pytest.fixture
def app() -> App:
    """A populated App with one doc and one tool."""
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


# --- learn ----------------------------------------------------------------


def test_learn_enumerates_doc_slugs(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "intro" in out
    assert "usage" in out


def test_learn_enumerates_tool_names(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "search" in out
    assert "index" in out


def test_learn_json_emits_valid_json(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "mytool"
    assert payload["version"] == "1.0.0"
    assert isinstance(payload["docs"], list)
    assert isinstance(payload["tools"], list)


def test_learn_json_docs_match_registry(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(app, ["learn", "--json"])
    payload = json.loads(capsys.readouterr().out)
    doc_slugs = {d["slug"] for d in payload["docs"]}
    assert doc_slugs == {d.slug for d in app.list_docs()}


def test_learn_json_tools_match_registry(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    run_cli(app, ["learn", "--json"])
    payload = json.loads(capsys.readouterr().out)
    tool_names = {t["name"] for t in payload["tools"]}
    assert tool_names == {t.name for t in app.list_tools()}


# --- doctor ----------------------------------------------------------------


def test_doctor_exits_zero_on_populated_app(app: App, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_cli(app, ["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "doc" in out.lower() or "tool" in out.lower()


def test_doctor_exits_zero_on_empty_app(capsys: pytest.CaptureFixture[str]) -> None:
    a = App(name="empty", version="0.1")
    rc = run_cli(a, ["doctor"])
    assert rc == 0


# --- unknown verb --------------------------------------------------------


def test_unknown_verb_exits_nonzero(app: App) -> None:
    rc = run_cli(app, ["bogus"])
    assert rc != 0


# --- make_cli returns parser ---------------------------------------------


def test_make_cli_returns_parser(app: App):
    parser = make_cli(app)
    assert parser is not None
    # It should have a parse_args method (argparse.ArgumentParser)
    assert hasattr(parser, "parse_args")
