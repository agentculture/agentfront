"""Unit tests for agentfront.App — the code-first SSOT config object (t1).

These encode t1's acceptance criteria:
  - one internal registry; every surface reads the same instance (no second store)
  - register-then-remove drops from the single enumeration
  - surfaces can only enumerate from the registry (no side-channel path)
"""

import pytest

import agentfront
from agentfront import App
from agentfront._registry import Registry


def test_app_exported_at_package_root():
    assert agentfront.App is App


def test_add_doc_text_and_path(tmp_path):
    app = App(name="t", version="1.0")
    app.add_doc(slug="inline", title="Inline", text="# Inline\nbody")
    md = tmp_path / "page.md"
    md.write_text("# Page\nfrom file", encoding="utf-8")
    app.add_doc(slug="file", title="File", path=str(md))
    assert {d.slug for d in app.list_docs()} == {"inline", "file"}
    assert app.get_doc("file").text == "# Page\nfrom file"


def test_add_doc_requires_text_or_path():
    app = App(name="t")
    with pytest.raises(ValueError):
        app.add_doc(slug="x", title="X")


def test_add_docs_dir_derives_slug_and_title(tmp_path):
    (tmp_path / "intro.md").write_text("# Introduction\nhi", encoding="utf-8")
    sub = tmp_path / "guide"
    sub.mkdir()
    (sub / "start.md").write_text("no heading here", encoding="utf-8")
    app = App(name="t")
    app.add_docs_dir(str(tmp_path))
    docs = {d.slug: d for d in app.list_docs()}
    assert set(docs) == {"intro", "guide/start"}
    assert docs["intro"].title == "Introduction"
    # falls back to the slug when there is no ATX heading
    assert docs["guide/start"].title == "guide/start"


def test_tool_decorator_bare():
    app = App(name="t")

    @app.tool
    def search(query: str) -> str:
        """Search."""
        return query

    assert search("hi") == "hi"  # original function still callable
    names = [t.name for t in app.list_tools()]
    assert names == ["search"]


def test_tool_decorator_with_args():
    app = App(name="t")

    @app.tool(name="lookup", description="Look it up")
    def f(q: str) -> str:
        return q

    entry = app.get_tool("lookup")
    assert entry.description == "Look it up"


def test_tool_direct_call():
    app = App(name="t")

    def f(q: str) -> str:
        """Doc."""
        return q

    app.tool(f)
    assert app.get_tool("f") is not None


# --- SSOT: one registry, every read goes through it ----------------------


def test_single_registry_no_second_store():
    app = App(name="t")
    # exactly one Registry instance on the App
    registries = [v for v in vars(app).values() if isinstance(v, Registry)]
    assert len(registries) == 1
    assert app.registry is registries[0]


def test_list_views_derive_from_the_registry():
    app = App(name="t")
    app.add_doc(slug="d", title="D", text="x")
    app.tool(lambda q: q, name="tool1")
    # the App's enumeration equals the registry's — no divergent copy
    assert app.list_docs() == app.registry.docs()
    assert app.list_tools() == app.registry.tools()


def test_register_then_remove_drops_from_enumeration():
    app = App(name="t")
    app.add_doc(slug="d", title="D", text="x")
    app.tool(lambda q: q, name="tool1")
    assert {d.slug for d in app.list_docs()} == {"d"}
    assert {t.name for t in app.list_tools()} == {"tool1"}
    app.remove_doc("d")
    app.remove_tool("tool1")
    assert app.list_docs() == []
    assert app.list_tools() == []


def test_no_side_channel_registration_path():
    """The only way onto a surface is through the registry.

    Asserted structurally: every public method that *adds* a doc/tool routes
    through the single registry, and there is no public ``App`` attribute that
    is a second container of docs/tools a surface could read instead.
    """
    app = App(name="t")
    app.add_doc(slug="d", title="D", text="x")
    app.tool(lambda q: q, name="tool1")
    containers = [
        v
        for k, v in vars(app).items()
        if isinstance(v, (list, dict, set)) and not k.startswith("_")
    ]
    # no stray list/dict/set holding state alongside the registry
    assert containers == []
    # a "surface" can only see what the registry holds
    assert app.list_docs() == app.registry.docs()
