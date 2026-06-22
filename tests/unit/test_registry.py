"""Unit tests for the single-source-of-truth Registry (t1)."""

import pytest

from agentfront._registry import (
    DocEntry,
    DuplicateError,
    Registry,
    ToolEntry,
    derive_input_schema,
)


def test_add_and_get_doc():
    reg = Registry()
    entry = reg.add_doc(slug="intro", title="Intro", text="# Intro\nbody")
    assert isinstance(entry, DocEntry)
    assert reg.get_doc("intro") is entry
    assert reg.docs() == [entry]


def test_remove_doc_drops_from_enumeration():
    reg = Registry()
    reg.add_doc(slug="a", title="A", text="a")
    reg.add_doc(slug="b", title="B", text="b")
    reg.remove_doc("a")
    assert [d.slug for d in reg.docs()] == ["b"]
    assert reg.get_doc("a") is None


def test_duplicate_doc_rejected():
    reg = Registry()
    reg.add_doc(slug="a", title="A", text="a")
    with pytest.raises(DuplicateError):
        reg.add_doc(slug="a", title="A2", text="a2")


def test_remove_missing_doc_raises():
    reg = Registry()
    with pytest.raises(KeyError):
        reg.remove_doc("nope")


def test_add_tool_derives_name_and_description():
    reg = Registry()

    def search(query: str) -> str:
        """Search the corpus."""
        return query

    entry = reg.add_tool(search)
    assert isinstance(entry, ToolEntry)
    assert entry.name == "search"
    assert entry.description == "Search the corpus."
    assert entry.func is search


def test_add_tool_name_and_description_overrides():
    reg = Registry()
    entry = reg.add_tool(lambda x: x, name="echo", description="Echo it")
    assert entry.name == "echo"
    assert entry.description == "Echo it"


def test_lambda_without_name_rejected():
    reg = Registry()
    with pytest.raises(ValueError):
        reg.add_tool(lambda x: x)


def test_duplicate_tool_rejected():
    reg = Registry()
    reg.add_tool(lambda x: x, name="t")
    with pytest.raises(DuplicateError):
        reg.add_tool(lambda x: x, name="t")


def test_derive_input_schema_types_and_required():
    def fn(a: str, b: int = 3, c: bool = False):
        return None

    schema = derive_input_schema(fn)
    assert schema["type"] == "object"
    assert schema["properties"] == {
        "a": {"type": "string"},
        "b": {"type": "integer"},
        "c": {"type": "boolean"},
    }
    # only the parameter without a default is required
    assert schema["required"] == ["a"]


def test_derive_input_schema_unannotated_defaults_to_string():
    def fn(x):
        return x

    schema = derive_input_schema(fn)
    assert schema["properties"]["x"] == {"type": "string"}


def test_derive_input_schema_skips_var_args_and_self():
    class C:
        def m(self, a: int, *args, **kwargs):
            return a

    schema = derive_input_schema(C.m)
    assert list(schema["properties"]) == ["a"]
