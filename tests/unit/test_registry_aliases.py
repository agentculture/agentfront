"""Unit tests for tool alias resolution (t6)."""

from agentfront._registry import Registry


def test_top_level_op_alias_resolves_to_same_entry():
    """A top-level op registered with aliases is reachable under each alias."""

    def backends_fn():
        return "ok"

    reg = Registry()
    reg.add_tool(backends_fn, name="backends", aliases=("wheels",))

    primary = reg.get_tool("backends")
    alias = reg.get_tool("wheels")

    assert primary is not None
    assert alias is primary


def test_top_level_alias_get_by_path():
    """get_by_path with an alias leaf resolves to the same entry."""

    def backends_fn():
        return "ok"

    reg = Registry()
    reg.add_tool(backends_fn, name="backends", aliases=("wheels",))

    assert reg.get_by_path(("wheels",)) is reg.get_by_path(("backends",))


def test_grouped_op_alias_resolves_within_group():
    """A grouped op with an alias resolves under both leaf names in its group."""

    def deploy_fn():
        return "ok"

    reg = Registry()
    reg.add_tool(deploy_fn, name="deploy", group=("ops",), aliases=("ship",))

    primary = reg.get_by_path(("ops", "deploy"))
    alias = reg.get_by_path(("ops", "ship"))

    assert primary is not None
    assert alias is primary


def test_list_tools_contains_entry_once():
    """aliases do not create duplicate entries in list_tools()."""

    def backends_fn():
        return "ok"

    reg = Registry()
    reg.add_tool(backends_fn, name="backends", aliases=("wheels", "tires"))

    tools = reg.tools()
    assert len(tools) == 1
    assert tools[0].name == "backends"
    assert tools[0].aliases == ("wheels", "tires")


def test_alias_not_registered_as_separate_key():
    """Removing by primary path works; alias path is not a separate key."""

    def backends_fn():
        return "ok"

    reg = Registry()
    reg.add_tool(backends_fn, name="backends", aliases=("wheels",))

    reg.remove_tool(("backends",))
    assert reg.get_tool("backends") is None
    assert reg.get_tool("wheels") is None


def test_no_aliases_default():
    """ToolEntry without aliases has empty tuple."""

    def simple_fn():
        return "ok"

    reg = Registry()
    entry = reg.add_tool(simple_fn, name="simple")
    assert entry.aliases == ()
