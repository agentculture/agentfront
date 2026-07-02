"""TAUI boundary guard — stdlib-only, no third-party deps, public API surface.

This test enforces the agent-first boundary for the agentfront.taui package:
every .py file must import only stdlib or agentfront modules, pyproject.toml
must not introduce a [taui] extra or any third-party dependency, and the
documented public callables must import cleanly.

It also runs a fresh-subprocess ``sys.modules`` scan (t8): a clean interpreter
imports ``agentfront.testing`` and every ``agentfront.taui`` submodule
discovered via ``pkgutil.iter_modules`` (recursively, so nested packages like
``render/`` and ``widgets/`` are covered, and a future module — e.g.
``session.py`` landing in a later wave — is picked up automatically without
editing this test) and must load no third-party package.
"""

from __future__ import annotations

import ast
import importlib
import json
import pkgutil
import subprocess  # noqa: S404 - integration test needs subprocess
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
    from agentfront.taui.derive import make_baseline
    from agentfront.taui.diagnose import diagnose
    from agentfront.taui.driver import Driver
    from agentfront.taui.mirror import serialize
    from agentfront.taui.reducer import reduce
    from agentfront.taui.render.ansi import render_ansi
    from agentfront.taui.render.markdown import render_markdown
    from agentfront.taui.selectors import resolve

    # Each documented public symbol imported above must be callable.
    assert all(
        callable(obj)
        for obj in (
            make_baseline,
            serialize,
            reduce,
            resolve,
            render_ansi,
            render_markdown,
            diagnose,
            Driver,
        )
    )


# ---------------------------------------------------------------------------
# Test 4: fresh-subprocess sys.modules scan (t8)
# ---------------------------------------------------------------------------


def _discover_taui_submodules() -> list[str]:
    """Every ``agentfront.taui`` module/subpackage, discovered via
    ``pkgutil.iter_modules`` (recursing into subpackages ourselves so nested
    packages like ``render/`` and ``widgets/`` are covered). A future module
    landing directly under ``agentfront/taui/`` — or under a new subpackage —
    is picked up automatically without editing this test.
    """

    def _walk(package_name: str) -> list[str]:
        package = importlib.import_module(package_name)
        found = [package_name]
        for info in pkgutil.iter_modules(package.__path__, prefix=f"{package_name}."):
            if info.ispkg:
                found.extend(_walk(info.name))
            else:
                found.append(info.name)
        return found

    return sorted(_walk("agentfront.taui"))


def test_taui_and_testing_subprocess_import_is_stdlib_only() -> None:
    """A fresh interpreter imports ``agentfront.testing`` plus every
    discovered ``agentfront.taui`` submodule; the resulting ``sys.modules``
    delta must contain no third-party top-level package.

    Runs in a genuinely clean subprocess (rather than an in-process
    ``sys.modules`` delta) so the check is not muddied by whatever pytest's
    own process already has loaded.
    """
    modules = _discover_taui_submodules()
    script = (
        "import sys\n"
        "before = set(sys.modules)\n"
        "import agentfront.testing\n"
        f"for name in {modules!r}:\n"
        "    __import__(name)\n"
        "after = set(sys.modules)\n"
        "import json\n"
        "print(json.dumps(sorted(after - before)))\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    new_modules = json.loads(result.stdout.strip().splitlines()[-1])
    stdlib = _stdlib_names()
    top_level = {mod.split(".")[0] for mod in new_modules}
    violations = {
        mod for mod in top_level if mod not in stdlib and not mod.startswith("agentfront")
    }
    assert not violations, f"Third-party modules loaded in subprocess: {sorted(violations)}"
