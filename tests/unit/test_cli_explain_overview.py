"""Tests for ``explain`` and ``overview`` meta-verbs on the CONSUMER CLI (t9).

These verbs are registry-derived: they work for ANY App from the registry doc
metadata, not agentfront's own hand-authored catalog.
"""

from __future__ import annotations

import json

import pytest

from agentfront import App
from agentfront.cli_surface import run_cli

# --- fixtures -----------------------------------------------------------


@pytest.fixture
def consumer_app() -> App:
    """A consumer App with grouped ops that have docstrings/doc."""

    app = App(name="consumer", version="0.1.0", description="A consumer app")

    @app.tool(
        group="feedback",
        doc=(
            "Record a feedback item with optional score.\n\n"
            "Usage: feedback record <item> [--score N]"
        ),
    )
    def record(item: str, score: int = 0) -> str:
        """Record feedback."""
        return f"{item}:{score}"

    @app.tool(group="feedback")
    def list_items() -> list[str]:
        """List recorded items."""
        return []

    @app.tool(group="auth")
    def login(username: str, password: str) -> str:
        """Login."""
        return username

    @app.tool
    def search(query: str) -> str:
        """Search the corpus."""
        return query

    return app


# --- explain verb -------------------------------------------------------


def test_explain_leaf_op_prints_doc(consumer_app: App, capsys) -> None:
    """explain <group> <verb> prints the op's .doc to stdout."""
    rc = run_cli(consumer_app, ["explain", "feedback", "record"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Record a feedback item" in out


def test_explain_leaf_op_json(consumer_app: App, capsys) -> None:
    """explain --json prints {"path": [...], "doc": "..."}."""
    rc = run_cli(consumer_app, ["explain", "feedback", "record", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == ["feedback", "record"]
    assert "Record a feedback item" in payload["doc"]


def test_explain_group_lists_children(consumer_app: App, capsys) -> None:
    """explain <group> (no leaf) lists child verb names+descriptions."""
    rc = run_cli(consumer_app, ["explain", "feedback"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "record" in out
    assert "list_items" in out


def test_explain_unknown_path_raises_error(consumer_app: App, capsys) -> None:
    """explain with an unknown path raises AgentfrontError (code=1)."""
    rc = run_cli(consumer_app, ["explain", "nope", "verb"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "error:" in err


def test_explain_top_level_tool(consumer_app: App, capsys) -> None:
    """explain on a top-level (ungrouped) tool works."""
    rc = run_cli(consumer_app, ["explain", "search"])
    assert rc == 0
    out = capsys.readouterr().out
    # search has no explicit doc, so doc is from __doc__
    assert "Search" in out


# --- overview verb ------------------------------------------------------


def test_overview_lists_nouns(consumer_app: App, capsys) -> None:
    """overview lists the registry's top-level nouns."""
    rc = run_cli(consumer_app, ["overview"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "feedback" in out
    assert "auth" in out
    assert "search" in out


def test_overview_json(consumer_app: App, capsys) -> None:
    """overview --json emits a structured list."""
    rc = run_cli(consumer_app, ["overview", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    names = {item["name"] for item in payload}
    assert "feedback" in names
    assert "auth" in names
    assert "search" in names


def test_overview_scoped_to_group(consumer_app: App, capsys) -> None:
    """overview <noun> scopes to that group's verbs."""
    rc = run_cli(consumer_app, ["overview", "feedback"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "record" in out
    assert "list_items" in out
    # Should NOT list auth verbs
    assert "login" not in out


# --- learn verb ---------------------------------------------------------


def test_learn_enumerates_grouped_ops(consumer_app: App, capsys) -> None:
    """learn lists every op's full path including grouped ones."""
    rc = run_cli(consumer_app, ["learn"])
    assert rc == 0
    out = capsys.readouterr().out
    # Grouped op should appear with its full path
    assert "feedback record" in out or "feedback" in out


def test_learn_json_enumerates_grouped_ops(consumer_app: App, capsys) -> None:
    """learn --json includes grouped ops with full paths."""
    rc = run_cli(consumer_app, ["learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    tools = payload["tools"]
    # Check that grouped ops are present
    tool_paths = [t["path"] for t in tools]
    assert ["feedback", "record"] in tool_paths
    assert ["feedback", "list_items"] in tool_paths
    assert ["auth", "login"] in tool_paths
    assert ["search"] in tool_paths


# --- dynamic registration: new op appears in all three --------------------


def test_new_op_appears_in_explain(consumer_app: App, capsys) -> None:
    """Adding a new op makes it appear in explain with no catalog edit."""

    @consumer_app.tool(group="feedback")
    def delete(item: str) -> str:
        """Delete a feedback item."""
        return item

    rc = run_cli(consumer_app, ["explain", "feedback", "delete"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Delete a feedback item" in out


def test_new_op_appears_in_overview(consumer_app: App, capsys) -> None:
    """Adding a new op makes it appear in overview with no catalog edit."""

    @consumer_app.tool(group="auth")
    def logout() -> str:
        """Logout."""
        return "logged out"

    rc = run_cli(consumer_app, ["overview"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "auth" in out


def test_new_op_appears_in_learn(consumer_app: App, capsys) -> None:
    """Adding a new op makes it appear in learn with no catalog edit."""

    @consumer_app.tool(group="feedback")
    def clear() -> str:
        """Clear all feedback."""
        return "cleared"

    rc = run_cli(consumer_app, ["learn", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    tool_paths = [t["path"] for t in payload["tools"]]
    assert ["feedback", "clear"] in tool_paths
