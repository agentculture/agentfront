"""Unit tests for the ToolEntry.doc metadata field (t4)."""

from agentfront._registry import Registry, ToolEntry


def test_explicit_doc_is_stored_on_tool_entry():
    """An op registered with explicit doc='...' has that doc on its ToolEntry."""

    def my_op(x: str) -> str:
        """Short description."""
        return x

    reg = Registry()
    entry = reg.add_tool(my_op, doc="## Custom doc\n\nFull markdown here.")
    assert isinstance(entry, ToolEntry)
    assert entry.doc == "## Custom doc\n\nFull markdown here."


def test_docstring_becomes_doc_when_no_explicit_doc():
    """An op with only a (multi-line) docstring gets its full dedented docstring as .doc."""

    def my_op(x: str) -> str:
        """Short description.

        This is the full body of the docstring.
        It spans multiple lines.
        """
        return x

    reg = Registry()
    entry = reg.add_tool(my_op)
    assert isinstance(entry, ToolEntry)
    # inspect.getdoc dedents the docstring
    expected = (
        "Short description.\n\nThis is the full body of the docstring.\nIt spans multiple lines."
    )
    assert entry.doc == expected


def test_doc_default_empty_when_no_docstring():
    """An op with no docstring gets an empty string as .doc."""

    def my_op(x: str) -> str:
        return x

    reg = Registry()
    entry = reg.add_tool(my_op)
    assert entry.doc == ""


def test_doc_retrievable_via_get_tool():
    """The op's .doc is retrievable from the registry via get_tool."""

    def my_op(x: str) -> str:
        """Short."""
        return x

    reg = Registry()
    reg.add_tool(my_op, doc="## Full doc")
    entry = reg.get_tool("my_op")
    assert entry is not None
    assert entry.doc == "## Full doc"


def test_doc_retrievable_via_get_by_path():
    """The op's .doc is retrievable from the registry via get_by_path."""

    def my_op(x: str) -> str:
        """Short."""
        return x

    reg = Registry()
    reg.add_tool(my_op, name="my_op", group=("grp",), doc="## Grouped doc")
    entry = reg.get_by_path(("grp", "my_op"))
    assert entry is not None
    assert entry.doc == "## Grouped doc"


def test_doc_retrievable_via_list_tools():
    """The op's .doc is retrievable from the registry via list_tools."""

    def my_op(x: str) -> str:
        """Short."""
        return x

    reg = Registry()
    reg.add_tool(my_op, doc="## Listed doc")
    tools = reg.tools()
    assert len(tools) == 1
    assert tools[0].doc == "## Listed doc"


def test_doc_and_description_are_independent():
    """The doc field is distinct from description; description stays the first line."""

    def my_op(x: str) -> str:
        """First line of docstring."""
        return x

    reg = Registry()
    entry = reg.add_tool(my_op, doc="## Separate doc")
    assert entry.description == "First line of docstring."
    assert entry.doc == "## Separate doc"
