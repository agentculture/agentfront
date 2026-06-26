"""Guard: the consumer CLI import path is pure stdlib + agentfront only.

Asserts:
  - Importing the consumer CLI modules does NOT pull any third-party package
    (specifically 'mcp' must not appear in sys.modules).
  - agentfront's declared runtime dependencies are empty in pyproject.toml.
  - 'mcp' only appears under the [mcp] optional extra.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Third-party top-level packages that must NOT be imported by the consumer CLI
# path.  We check a representative set — any well-known third-party name.
_THIRD_PARTY_PACKAGES = frozenset(
    {
        "mcp",
        "click",
        "typer",
        "rich",
        "pydantic",
        "fastapi",
        "uvicorn",
        "httpx",
        "requests",
        "flask",
        "starlette",
        "anyio",
        "sniffio",
        "syrupy",
        "pytest",
        "coverage",
        "black",
        "isort",
        "flake8",
        "pylint",
        "bandit",
        "pre_commit",
        "hatchling",
    }
)

# Modules in the consumer CLI import path that must be stdlib + agentfront only.
# We import the top-level consumer-facing modules; internal modules (e.g.
# _cli_core) are pulled in transitively and checked via the sys.modules delta.
_CONSUMER_CLI_MODULES = [
    "agentfront.app",
    "agentfront.cli_surface",
    "agentfront._registry",
    "agentfront.errors",
    "agentfront.cli._output",
]


def _get_pyproject() -> Path:
    """Return the repo root pyproject.toml."""
    return Path(__file__).resolve().parents[2] / "pyproject.toml"


def _read_dependencies(pyproject: Path) -> dict[str, list[str]]:
    """Parse the minimal subset of pyproject.toml we need.

    Returns a dict mapping section key to list of dependency strings.
    We only need [project].dependencies and
    [project.optional-dependencies].
    """
    text = pyproject.read_text(encoding="utf-8")
    result: dict[str, list[str]] = {}
    current_section: str | None = None
    current_list: list[str] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            # New section
            if current_section is not None and current_list is not None:
                result[current_section] = current_list
            current_section = stripped
            current_list = []
            continue
        if current_section is not None and current_list is not None:
            if stripped.startswith('"') or stripped.startswith("'"):
                # Inline table entry (e.g. "mcp>=1.28.0",)
                dep = stripped.strip(",").strip('"').strip("'")
                if dep:
                    current_list.append(dep)
            elif stripped.startswith("#"):
                continue
            elif stripped == "":
                continue
            elif stripped.startswith("dependencies"):
                # Could be a key in a section; skip
                pass

    if current_section is not None and current_list is not None:
        result[current_section] = current_list

    return result


def _parse_deps_simple(pyproject: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Parse runtime deps and optional extras from pyproject.toml.

    Returns (runtime_deps, {extra_name: [dep, ...]}).
    """
    text = pyproject.read_text(encoding="utf-8")
    lines = text.splitlines()

    runtime_deps: list[str] = []
    extras: dict[str, list[str]] = {}

    section: str | None = None
    extra_name: str | None = None

    for line in lines:
        stripped = line.strip()

        # Section headers
        if stripped.startswith("["):
            section = stripped
            extra_name = None
            continue

        if section == "[project]":
            # Look for dependencies = [...]
            if stripped.startswith("dependencies"):
                # Could be inline: dependencies = []
                eq_idx = stripped.index("=") if "=" in stripped else -1
                if eq_idx >= 0:
                    value = stripped[eq_idx + 1 :].strip()
                    if value.startswith("[") and value.endswith("]"):
                        # Inline list
                        inner = value[1:-1].strip()
                        if inner:
                            for item in inner.split(","):
                                dep = item.strip().strip('"').strip("'")
                                if dep:
                                    runtime_deps.append(dep)
                        else:
                            runtime_deps = []
                    # Multi-line list handled below
                continue
            # Collect multi-line list items under [project]
            if stripped.startswith('"') or stripped.startswith("'"):
                dep = stripped.strip(",").strip('"').strip("'")
                if dep:
                    runtime_deps.append(dep)

        elif section and section.startswith("[project.optional-dependencies]"):
            # Detect extra name = [
            if "=" in stripped and not stripped.startswith('"'):
                eq_idx = stripped.index("=")
                left = stripped[:eq_idx].strip()
                right = stripped[eq_idx + 1 :].strip()
                if right.startswith("["):
                    extra_name = left
                    extras.setdefault(extra_name, [])
                    inner = right[1:].strip().rstrip("]")
                    if inner:
                        for item in inner.split(","):
                            dep = item.strip().strip('"').strip("'")
                            if dep:
                                extras[extra_name].append(dep)
                continue
            if extra_name is not None:
                if stripped.startswith('"') or stripped.startswith("'"):
                    dep = stripped.strip(",").strip('"').strip("'")
                    if dep:
                        extras[extra_name].append(dep)
                elif stripped == "]":
                    extra_name = None

    return runtime_deps, extras


class TestConsumerCliStdlib:
    """Guard: consumer CLI imports only stdlib + agentfront."""

    def test_no_third_party_in_sys_modules_after_import(self) -> None:
        """Importing the consumer CLI path must not pull third-party packages."""
        # Snapshot modules before import
        before = set(sys.modules.keys())

        # Fresh-import each module in the consumer CLI path
        for mod_name in _CONSUMER_CLI_MODULES:
            if mod_name in sys.modules:
                # Already imported; skip but still check
                pass
            else:
                importlib.import_module(mod_name)

        # Check newly imported modules
        after = set(sys.modules.keys())
        new_modules = after - before

        # Filter to top-level package names
        new_top_level = {m.split(".")[0] for m in new_modules}

        violations = new_top_level & _THIRD_PARTY_PACKAGES
        assert (
            not violations
        ), f"Consumer CLI path imported third-party packages: {sorted(violations)}"

    def test_mcp_not_in_sys_modules_after_cli_usage(self) -> None:
        """Building an App and calling cli()/run_cli must not import 'mcp'."""
        # Ensure mcp is not already loaded (it might be from dev deps)
        # We can't evict it if already loaded, so we check the import chain
        # by tracking what new modules appear.
        before = set(sys.modules.keys())

        from agentfront import App
        from agentfront.cli_surface import make_cli, run_cli

        app = App(name="test", version="0.1")

        @app.tool
        def hello(name: str) -> str:
            return f"hello {name}"

        # Build the CLI
        parser = make_cli(app)
        assert parser is not None

        # Run the CLI
        rc = run_cli(app, ["hello", "world"])
        assert rc == 0

        after = set(sys.modules.keys())
        new_modules = after - before
        new_top_level = {m.split(".")[0] for m in new_modules}

        assert (
            "mcp" not in new_top_level
        ), "mcp was imported during CLI usage — it should only load via mcp_server()"

    def test_runtime_dependencies_are_empty(self) -> None:
        """agentfront's [project].dependencies must be empty."""
        pyproject = _get_pyproject()
        runtime_deps, _ = _parse_deps_simple(pyproject)
        assert runtime_deps == [], (
            f"agentfront has runtime dependencies: {runtime_deps}; " "core must be pure stdlib"
        )

    def test_mcp_only_in_optional_extra(self) -> None:
        """'mcp' must only appear under [project.optional-dependencies].mcp."""
        pyproject = _get_pyproject()
        runtime_deps, extras = _parse_deps_simple(pyproject)

        # Runtime deps must not contain mcp
        runtime_names = {
            d.split(">")[0].split("<")[0].split("=")[0].split("[")[0] for d in runtime_deps
        }
        assert "mcp" not in runtime_names, "mcp must not be a runtime dependency"

        # mcp must be in the optional extras
        assert "mcp" in extras, "mcp must be declared under [project.optional-dependencies]"

        # The mcp extra must contain the mcp SDK
        mcp_extra = extras["mcp"]
        mcp_sdk_names = {
            d.split(">")[0].split("<")[0].split("=")[0].split("[")[0] for d in mcp_extra
        }
        assert "mcp" in mcp_sdk_names, f"[mcp] extra must contain the mcp SDK; got {mcp_extra}"
