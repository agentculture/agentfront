"""Unit tests for agentfront.taui.derive — make_baseline."""

from __future__ import annotations

from agentfront import App
from agentfront.taui.derive import make_baseline
from agentfront.taui.state import Header


def _make_fixture() -> App:
    """Return an App with grouped tools, ungrouped tools, aliases, and a host command."""
    app = App(name="TestApp", version="0.2.0", description="A test app")

    @app.tool(group=("feedback",), aliases=("f",))
    def record(msg: str) -> str:
        """Record feedback."""
        return msg

    @app.tool(group=("feedback",))
    def list_items() -> list[str]:
        """List feedback items."""
        return []

    @app.tool(group=("search",), aliases=("s", "find"))
    def query(text: str) -> str:
        """Search the corpus."""
        return text

    @app.tool
    def status() -> str:
        """Check status."""
        return "ok"

    def _status_handler() -> None:
        pass

    app.add_command("deploy", _status_handler, help="Deploy the app", aliases=("d",))

    return app


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def test_header_populated_from_app() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    assert state.header == Header(
        title="TestApp",
        subtitle="A test app",
        version="0.2.0",
    )


# ---------------------------------------------------------------------------
# Panels — one per group plus root
# ---------------------------------------------------------------------------


def test_panel_ids() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    panel_ids = [p.id for p in state.panels]
    # "feedback", "root", "search" — sorted
    assert panel_ids == ["feedback", "root", "search"]


def test_panel_titles() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    titles = {p.id: p.title for p in state.panels}
    assert titles["feedback"] == "feedback"
    assert titles["search"] == "search"
    assert titles["root"] == ""


# ---------------------------------------------------------------------------
# PanelItems — every tool and command appears exactly once
# ---------------------------------------------------------------------------


def test_all_items_present() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    item_ids: list[str] = []
    for panel in state.panels:
        item_ids.extend(i.id for i in panel.items)

    # Sorted by id within each panel, panels sorted by id
    assert item_ids == [
        "feedback.list_items",
        "feedback.record",
        "deploy",
        "status",
        "search.query",
    ]


def test_items_sorted_within_panel() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    for panel in state.panels:
        ids = [i.id for i in panel.items]
        assert ids == sorted(ids)


def test_panels_sorted_by_id() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    ids = [p.id for p in state.panels]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Aliases — tags on the canonical item, not duplicate items
# ---------------------------------------------------------------------------


def test_alias_tags_on_tool() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    # feedback.record has alias "f" -> "alias:feedback.f"
    record_item = next(i for p in state.panels for i in p.items if i.id == "feedback.record")
    assert "alias:feedback.f" in record_item.tags


def test_alias_tags_on_search_tool() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    query_item = next(i for p in state.panels for i in p.items if i.id == "search.query")
    assert "alias:search.s" in query_item.tags
    assert "alias:search.find" in query_item.tags


def test_alias_tags_on_host_command() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    deploy_item = next(i for p in state.panels for i in p.items if i.id == "deploy")
    assert "alias:d" in deploy_item.tags


def test_no_duplicate_items_for_aliases() -> None:
    """Aliases must NOT create separate PanelItems."""
    app = _make_fixture()
    state = make_baseline(app)
    all_ids: list[str] = []
    for panel in state.panels:
        all_ids.extend(i.id for i in panel.items)

    # "feedback.f" and "search.s" / "search.find" must NOT appear as ids
    assert "feedback.f" not in all_ids
    assert "search.s" not in all_ids
    assert "search.find" not in all_ids


# ---------------------------------------------------------------------------
# Labels and status
# ---------------------------------------------------------------------------


def test_tool_label_uses_description() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    record_item = next(i for p in state.panels for i in p.items if i.id == "feedback.record")
    assert record_item.label == "Record feedback."


def test_tool_status_available() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    for panel in state.panels:
        for item in panel.items:
            assert item.status == "available"


def test_host_command_label_uses_help() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    deploy_item = next(i for p in state.panels for i in p.items if i.id == "deploy")
    assert deploy_item.label == "Deploy the app"


# ---------------------------------------------------------------------------
# Ungrouped tool goes to root panel
# ---------------------------------------------------------------------------


def test_ungrouped_tool_in_root() -> None:
    app = _make_fixture()
    state = make_baseline(app)
    root_panel = next(p for p in state.panels if p.id == "root")
    root_ids = [i.id for i in root_panel.items]
    assert "status" in root_ids


# ---------------------------------------------------------------------------
# Empty app
# ---------------------------------------------------------------------------


def test_empty_app() -> None:
    app = App(name="Empty")
    state = make_baseline(app)
    assert state.header.title == "Empty"
    assert state.panels == []
