"""TAUI boundary guard — stdlib-only, no third-party deps, public API surface.

This test enforces the agent-first boundary for the agentfront.taui package:
every .py file must import only stdlib or agentfront modules, pyproject.toml
must not introduce a [taui] extra or any third-party dependency, and the
documented public callables must import cleanly.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TAUUI_DIR = _REPO_ROOT / "agentfront" / "taui"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

_FORBIDDEN_MODULES = frozenset({"textual", "rich", "blessed", "urwid", "curses", "prompt_toolkit"})


def _stdlib_names() -> frozenset[str]:
    """Return the set of stdlib module names (Python 3.12+)."""
    return frozenset(sys.stdlib_module_names)


def _top_level_imports(tree: ast.Module) -> list[str]:
    """Extract top-level module names from import/ImportFrom nodes."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                names.append(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# Test 1: No third-party runtime dependency
# ---------------------------------------------------------------------------


def test_taui_stdlib_only_imports():
    """Every .py under agentfront/taui/ imports only stdlib or agentfront."""
    stdlib = _stdlib_names()
    violations: list[str] = []

    for pyfile in sorted(_TAUUI_DIR.rglob("*.py")):
        source = pyfile.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(pyfile))
        for mod in _top_level_imports(tree):
            if mod.startswith("agentfront"):
                continue
            if mod in stdlib:
                continue
            violations.append(f"{pyfile.relative_to(_REPO_ROOT)}: {mod}")

    assert not violations, "Third-party imports found in agentfront/taui:\n" + "\n".join(violations)


def test_taui_no_forbidden_tui_frameworks():
    """None of the forbidden TUI frameworks are imported anywhere in taui."""
    for pyfile in sorted(_TAUUI_DIR.rglob("*.py")):
        source = pyfile.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(pyfile))
        for mod in _top_level_imports(tree):
            assert (
                mod not in _FORBIDDEN_MODULES
            ), f"Forbidden module {mod!r} imported in {pyfile.relative_to(_REPO_ROOT)}"


# ---------------------------------------------------------------------------
# Test 2: No [taui] extra / no new base dependency
# ---------------------------------------------------------------------------


def test_pyproject_no_taui_extra():
    """pyproject.toml must not have a 'taui' optional-dependencies key."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    optional = data.get("project", {}).get("optional-dependencies", {})
    assert (
        "taui" not in optional
    ), "A 'taui' optional-dependencies key must not exist in pyproject.toml"


def test_pyproject_no_third_party_deps():
    """'textual' and 'rich' must not appear in any dependency list."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})

    # Check direct dependencies.
    deps = project.get("dependencies", [])
    for dep in deps:
        name = dep.split("[")[0].split("=")[0].split(">")[0].split("<")[0].split(";")[0].strip()
        assert name not in {
            "textual",
            "rich",
        }, f"Third-party dep {name!r} found in project.dependencies"

    # Check optional-dependencies.
    for extra, extra_deps in project.get("optional-dependencies", {}).items():
        for dep in extra_deps:
            name = dep.split("[")[0].split("=")[0].split(">")[0].split("<")[0].split(";")[0].strip()
            assert name not in {
                "textual",
                "rich",
            }, f"Third-party dep {name!r} found in optional-dependencies['{extra}']"


# ---------------------------------------------------------------------------
# Test 3: Public API surface imports cleanly
# ---------------------------------------------------------------------------


def test_taui_public_api_imports():
    """All documented public callables import without error."""
    from agentfront.taui.derive import make_baseline  # noqa: F401
    from agentfront.taui.diagnose import diagnose  # noqa: F401
    from agentfront.taui.driver import Driver  # noqa: F401
    from agentfront.taui.mirror import serialize  # noqa: F401
    from agentfront.taui.reducer import reduce  # noqa: F401
    from agentfront.taui.render.ansi import render_ansi  # noqa: F401
    from agentfront.taui.render.markdown import render_markdown  # noqa: F401
    from agentfront.taui.selectors import resolve  # noqa: F401

    # If we got here, all imports succeeded.
    assert True
