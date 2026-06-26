"""Unit tests for nested group support in the Registry (t3).

Asserts:
  - @app.tool(group='feedback') yields group=('feedback',) and full path ('feedback', <name>)
  - app.group('feedback') sub-registrar yields path ('feedback', <name>)
  - nested app.group('a').group('b') yields ('a', 'b', <name>)
  - leaf ops resolve by full path via get_by_path
  - existing top-level ops (no group) still enumerate via list_tools() and resolve via get_tool(name)
"""

from __future__ import annotations

import pytest

from agentfront import App
from agentfront._registry import Registry, ToolEntry

# --- ToolEntry group field -----------------------------------------------


def test_tool_entry_has_group_field():
    entry = ToolEntry(
        name="ping",
        description="Ping",
        input_schema={"type": "object", "properties": {}},
        func=lambda: None,
        group=(),
    )
    assert entry.group == ()


def test_tool_entry_grouped():
    entry = ToolEntry(
        name="ping",
        description="Ping",
        input_schema={"type": "object", "properties": {}},
        func=lambda: None,
        group=("feedback",),
    )
    assert entry.group == ("feedback",)


# --- Registry add_tool with group ----------------------------------------


def test_registry_add_tool_with_group():
    reg = Registry()

    def f():
        return 1

    entry = reg.add_tool(f, name="ping", group=("feedback",))
    assert entry.group == ("feedback",)
    assert entry.name == "ping"


def test_registry_add_tool_no_group_is_top_level():
    reg = Registry()

    def f():
        return 1

    entry = reg.add_tool(f, name="ping")
    assert entry.group == ()


def test_registry_tools_enumerates_grouped_and_top_level():
    reg = Registry()

    def top():
        return 1

    def nested():
        return 2

    reg.add_tool(top, name="top")
    reg.add_tool(nested, name="nested", group=("feedback",))
    tools = reg.tools()
    names = [t.name for t in tools]
    assert "top" in names
    assert "nested" in names


def test_registry_get_tool_finds_top_level():
    reg = Registry()

    def f():
        return 1

    reg.add_tool(f, name="ping")
    assert reg.get_tool("ping") is not None


def test_registry_get_tool_does_not_find_grouped_by_name():
    """Grouped tools are keyed by full path, not bare name."""
    reg = Registry()

    def f():
        return 1

    reg.add_tool(f, name="ping", group=("feedback",))
    # bare name lookup should NOT find it (it's under a group)
    assert reg.get_tool("ping") is None


def test_registry_get_by_path_resolves_grouped_tool():
    reg = Registry()

    def f():
        return 1

    reg.add_tool(f, name="ping", group=("feedback",))
    entry = reg.get_by_path(("feedback", "ping"))
    assert entry is not None
    assert entry.name == "ping"
    assert entry.group == ("feedback",)


def test_registry_get_by_path_resolves_top_level_tool():
    """Top-level tools resolve via their bare name as path."""
    reg = Registry()

    def f():
        return 1

    reg.add_tool(f, name="ping")
    entry = reg.get_by_path(("ping",))
    assert entry is not None
    assert entry.name == "ping"


def test_registry_get_by_path_missing_returns_none():
    reg = Registry()
    assert reg.get_by_path(("feedback", "ping")) is None


def test_registry_duplicate_path_rejected():
    reg = Registry()

    def f1():
        return 1

    def f2():
        return 2

    reg.add_tool(f1, name="ping", group=("feedback",))
    with pytest.raises(Exception):  # DuplicateError
        reg.add_tool(f2, name="ping", group=("feedback",))


def test_registry_same_name_different_groups_allowed():
    """Two tools named 'ping' under different groups are distinct."""
    reg = Registry()

    def f1():
        return 1

    def f2():
        return 2

    reg.add_tool(f1, name="ping", group=("feedback",))
    reg.add_tool(f2, name="ping", group=("auth",))
    assert reg.get_by_path(("feedback", "ping")) is not None
    assert reg.get_by_path(("auth", "ping")) is not None


def test_registry_remove_tool_by_path():
    reg = Registry()

    def f():
        return 1

    reg.add_tool(f, name="ping", group=("feedback",))
    reg.remove_tool(("feedback", "ping"))
    assert reg.get_by_path(("feedback", "ping")) is None


# --- App.tool(group=...) ------------------------------------------------


def test_app_tool_with_str_group():
    app = App(name="t")

    @app.tool(group="feedback")
    def rate(score: int) -> int:
        """Rate something."""
        return score

    entry = app.get_by_path(("feedback", "rate"))
    assert entry is not None
    assert entry.group == ("feedback",)


def test_app_tool_with_tuple_group():
    app = App(name="t")

    @app.tool(group=("feedback", "internal"))
    def rate(score: int) -> int:
        """Rate something."""
        return score

    entry = app.get_by_path(("feedback", "internal", "rate"))
    assert entry is not None
    assert entry.group == ("feedback", "internal")


# --- App.group() sub-registrar -----------------------------------------


def test_app_group_returns_sub_registrar():
    app = App(name="t")
    registrar = app.group("feedback")

    @registrar.tool
    def rate(score: int) -> int:
        """Rate."""
        return score

    entry = app.get_by_path(("feedback", "rate"))
    assert entry is not None
    assert entry.group == ("feedback",)


def test_app_group_nested():
    app = App(name="t")
    registrar = app.group("a").group("b")

    @registrar.tool
    def deep(x: int) -> int:
        """Deep."""
        return x

    entry = app.get_by_path(("a", "b", "deep"))
    assert entry is not None
    assert entry.group == ("a", "b")


# --- Backward compatibility: top-level ops unchanged ---------------------


def test_top_level_tool_still_in_list_tools():
    app = App(name="t")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    tools = app.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "search"
    assert tools[0].group == ()


def test_top_level_tool_resolves_via_get_tool():
    app = App(name="t")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    assert app.get_tool("search") is not None


def test_grouped_tool_not_in_get_tool():
    """Grouped tools don't show up in bare get_tool(name)."""
    app = App(name="t")

    @app.tool(group="feedback")
    def rate(score: int) -> int:
        """Rate."""
        return score

    assert app.get_tool("rate") is None


def test_list_tools_includes_both_grouped_and_top_level():
    app = App(name="t")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    @app.tool(group="feedback")
    def rate(score: int) -> int:
        """Rate."""
        return score

    tools = app.list_tools()
    names = [t.name for t in tools]
    assert "search" in names
    assert "rate" in names
