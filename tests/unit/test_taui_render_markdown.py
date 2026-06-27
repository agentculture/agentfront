"""Unit tests for agentfront.taui.render.markdown — render_markdown."""

from __future__ import annotations

import ast
import importlib
import inspect

from agentfront.taui.render.markdown import render_markdown
from agentfront.taui.state import Header, Panel, PanelItem, Status, TAUIState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    title: str = "MyApp",
    version: str = "0.1.0",
    subtitle: str = "Test app",
    focused: str = "search.query",
    status: Status | None = None,
    panels: list[Panel] | None = None,
) -> TAUIState:
    """Return a representative TAUIState for rendering tests."""
    if status is None:
        status = Status(severity="info", message="Ready")
    if panels is None:
        panels = [
            Panel(
                id="search",
                title="Search",
                visible=True,
                items=[
                    PanelItem(id="search.query", label="Query", status="available"),
                    PanelItem(id="search.advanced", label="Advanced", status="disabled"),
                ],
            ),
            Panel(
                id="feedback",
                title="Feedback",
                visible=False,
                items=[
                    PanelItem(id="feedback.record", label="Record", status="available"),
                ],
            ),
        ]
    return TAUIState(
        header=Header(title=title, version=version, subtitle=subtitle),
        focused=focused,
        status=status,
        panels=panels,
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_render_markdown_is_deterministic() -> None:
    """Same state always produces identical markdown output."""
    state = _make_state()
    result_a = render_markdown(state)
    result_b = render_markdown(state)
    assert result_a == result_b


# ---------------------------------------------------------------------------
# Stdlib-only (no third-party imports)
# ---------------------------------------------------------------------------


def test_render_markdown_stdlib_only() -> None:
    """The module must not import any third-party packages."""
    module = importlib.import_module("agentfront.taui.render.markdown")
    source = inspect.getsource(module)
    tree = ast.parse(source)

    stdlib_names = {
        "__future__",
        "agentfront",
        "dataclasses",
        "typing",
        "collections",
        "collections.abc",
        "os",
        "sys",
        "re",
        "json",
        "pathlib",
        "itertools",
        "functools",
        "abc",
        "enum",
        "textwrap",
        "string",
        "io",
        "math",
        "time",
        "datetime",
        "copy",
        "types",
        "warnings",
        "logging",
        "threading",
        "multiprocessing",
        "subprocess",
        "shutil",
        "tempfile",
        "glob",
        "fnmatch",
        "hashlib",
        "hmac",
        "base64",
        "binascii",
        "struct",
        "codecs",
        "unicodedata",
        "csv",
        "configparser",
        "xml",
        "html",
        "urllib",
        "http",
        "email",
        "socket",
        "ssl",
        "select",
        "selectors",
        "signal",
        "mmap",
        "ctypes",
        "concurrent",
        "asyncio",
        "contextlib",
        "contextvars",
        "weakref",
        "array",
        "queue",
        "heapq",
        "bisect",
        "pprint",
        "reprlib",
        "traceback",
        "dis",
        "pickle",
        "shelve",
        "dbm",
        "sqlite3",
        "gzip",
        "bz2",
        "lzma",
        "zipfile",
        "tarfile",
        "zlib",
        "unittest",
        "doctest",
        "profile",
        "cProfile",
        "timeit",
        "trace",
        "pdb",
        "gc",
        "atexit",
        "errno",
        "stat",
        "fileinput",
        "filecmp",
        "locale",
        "gettext",
        "argparse",
        "getopt",
        "platform",
        "uuid",
        "decimal",
        "fractions",
        "random",
        "statistics",
        "cmath",
        "operator",
        "keyword",
        "token",
        "tokenize",
        "compileall",
        "py_compile",
        "symtable",
        "tabnanny",
        "builtins",
        "importlib",
        "pkgutil",
        "modulefinder",
        "runpy",
        "site",
        "code",
        "codeop",
        "pydoc",
        "distutils",
        "venv",
        "ensurepip",
        "pip",
        "setuptools",
        "wheel",
        "inspect",
        "ast",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_names, f"Third-party import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                top = node.module.split(".")[0]
                assert top in stdlib_names, f"Third-party import from: {node.module}"


# ---------------------------------------------------------------------------
# Header rendering
# ---------------------------------------------------------------------------


def test_header_title_appears() -> None:
    state = _make_state(title="MyApp")
    md = render_markdown(state)
    assert "# MyApp" in md


def test_header_version_and_subtitle_appear() -> None:
    state = _make_state(version="1.2.3", subtitle="A subtitle")
    md = render_markdown(state)
    assert "1.2.3" in md
    assert "A subtitle" in md


# ---------------------------------------------------------------------------
# Status rendering
# ---------------------------------------------------------------------------


def test_status_section_present() -> None:
    state = _make_state()
    md = render_markdown(state)
    assert "## Status" in md


def test_status_severity_and_message_appear() -> None:
    state = _make_state(status=Status(severity="warning", message="Low disk"))
    md = render_markdown(state)
    assert "warning" in md
    assert "Low disk" in md


# ---------------------------------------------------------------------------
# Panel rendering
# ---------------------------------------------------------------------------


def test_visible_panel_heading_appears() -> None:
    state = _make_state()
    md = render_markdown(state)
    assert "## Search" in md


def test_hidden_panel_does_not_appear() -> None:
    state = _make_state()
    md = render_markdown(state)
    assert "## Feedback" not in md


def test_panel_items_listed() -> None:
    state = _make_state()
    md = render_markdown(state)
    assert "- Query (available)" in md
    assert "- Advanced (disabled)" in md


def test_focused_item_marked() -> None:
    state = _make_state(focused="search.query")
    md = render_markdown(state)
    assert "**(focused)**" in md
    assert "- Query (available) **(focused)**" in md


def test_non_focused_item_not_marked() -> None:
    state = _make_state(focused="search.query")
    md = render_markdown(state)
    # The "Advanced" item should NOT have the focused marker
    assert "- Advanced (disabled) **(focused)**" not in md


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_state() -> None:
    """A default TAUIState renders without error."""
    state = TAUIState()
    md = render_markdown(state)
    assert isinstance(md, str)
    assert len(md) > 0


def test_no_panels() -> None:
    """State with no panels still renders header and status."""
    state = TAUIState(panels=[])
    md = render_markdown(state)
    assert "## Status" in md
    assert "## " not in md.split("## Status")[0].split("\n")[-1]  # no extra ## before status


def test_all_panels_hidden() -> None:
    """When all panels are hidden, no panel sections appear."""
    state = TAUIState(
        panels=[
            Panel(id="p1", title="Hidden", visible=False, items=[]),
        ]
    )
    md = render_markdown(state)
    assert "## Hidden" not in md


def test_multiple_visible_panels() -> None:
    """Multiple visible panels each get their own section."""
    state = TAUIState(
        panels=[
            Panel(
                id="a",
                title="Alpha",
                visible=True,
                items=[PanelItem(id="a1", label="One", status="ok")],
            ),
            Panel(
                id="b",
                title="Beta",
                visible=True,
                items=[PanelItem(id="b1", label="Two", status="pending")],
            ),
        ]
    )
    md = render_markdown(state)
    assert "## Alpha" in md
    assert "## Beta" in md
    assert "- One (ok)" in md
    assert "- Two (pending)" in md
