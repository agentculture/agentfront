"""CLI-subject inspector — descriptive snapshot of a target CLI project.

Inspection strategy — **static only**. No subprocesses are spawned in the
target (that's what ``agentfront cli doctor`` is for; ``overview`` is the cheap
read-only survey that runs in milliseconds and never imports foreign code).

Two modes:

* **Target mode** — ``path`` points at a project with ``pyproject.toml`` +
  ``[project.scripts]``. We derive the module from the first script entry,
  walk ``<path>/<module>/cli/_commands/`` to enumerate the command surface,
  and scan each noun module's source for ``sub.add_parser("...")`` calls
  (best-effort — static regex, not a real AST).

* **Zero-target mode** — ``path`` is ``None`` or the target has no
  pyproject (fresh project, caller just wants to know what agentfront is).
  We describe agentfront's own runtime model — the importable :class:`App`
  that derives the CLI / MCP / HTTP surfaces from one registry, and the
  agent-first universal verbs every surface ships. No file is read; the
  description is deterministic and complete.

The module never raises on inspection failure; it emits ``> ⚠️`` warnings
into the report and returns the best partial view it has. Callers get a
useful answer even on malformed targets.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agentfront.overview import OverviewReport, OverviewSection

# Module-internal regex cache. Best-effort; a target CLI whose parser wiring
# uses a format the regex can't see is reported with a warning, not a crash.
_ADD_PARSER_RE = re.compile(r'add_parser\(\s*[\'"]([^\'"]+)[\'"]')

# Agent-first universal verbs. v0.5 expanded the set from the introspection
# triple (learn/explain/overview) to include the diagnosability pillar
# (doctor); the constant name avoids fixed arity ("triple") so it can grow
# further if agentfront mandates another verb in a future version.
_UNIVERSAL_VERBS = ("learn", "explain", "overview", "doctor")


@dataclass
class _TargetInfo:
    """Resolved static metadata about a target project."""

    path: Path
    project_name: str | None
    script_name: str
    module_target: str  # e.g. "agentfront.cli:main"
    package_module: str  # e.g. "agentfront.cli" (the :main half stripped)
    package_root: Path  # e.g. <path>/agentfront/cli/


def inspect(path: Path | None) -> OverviewReport:
    """Produce a CLI-surface overview report.

    ``path`` is the target project root (``None`` triggers the zero-target
    fallback). The returned report is always renderable — malformed input
    becomes warnings, never exceptions.
    """
    if path is None:
        return _zero_target_report()

    target = path.resolve()
    if not target.exists():
        return _zero_target_report(
            warning=(
                f"path does not exist: {target}; falling back to " "agentfront's runtime model."
            ),
            attempted_path=str(target),
        )

    pyproject = target / "pyproject.toml"
    if not pyproject.is_file():
        return _zero_target_report(
            warning=(
                f"no pyproject.toml at {pyproject}; target has no detectable CLI surface, "
                "falling back to agentfront's runtime model."
            ),
            attempted_path=str(target),
        )

    info, parse_warnings = _resolve_target_info(target, pyproject)
    if info is None:
        # _resolve_target_info returned warnings but could not identify a script.
        report = _zero_target_report(
            warning=(
                f"{pyproject} has no usable [project.scripts] entry; "
                "falling back to agentfront's runtime model."
            ),
            attempted_path=str(target),
        )
        report.warnings.extend(parse_warnings)
        return report

    report = OverviewReport(subject="cli", path=str(target))
    report.warnings.extend(parse_warnings)
    _emit_project_root_section(report, info)
    _emit_command_surface_section(report, info)
    _emit_agent_first_triple_section(report, info)
    _emit_rubric_posture_section(report, info)
    report.notes.append(
        f"deeper walk: read {info.package_root}/_commands/*.py directly for the "
        "full verb wiring — overview uses best-effort static regex."
    )
    report.notes.append(f"for rubric grading (pass/fail), run: agentfront cli doctor {target}")
    return report


# ---------------------------------------------------------------------------
# Target-mode helpers
# ---------------------------------------------------------------------------


def _resolve_target_info(target: Path, pyproject: Path) -> tuple[_TargetInfo | None, list[str]]:
    warnings: list[str] = []
    try:
        data = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError) as err:
        warnings.append(f"could not parse {pyproject}: {err}")
        return None, warnings

    project = data.get("project", {}) if isinstance(data, dict) else {}
    project_name = project.get("name") if isinstance(project, dict) else None
    scripts = project.get("scripts", {}) if isinstance(project, dict) else {}
    if not isinstance(scripts, dict) or not scripts:
        return None, warnings

    # First entry is authoritative for overview purposes. Users with multiple
    # entry points can run `agentfront cli overview` once per entry in future
    # iterations; v0.3 inspects the first and notes the others.
    script_name, module_target = next(iter(scripts.items()))
    if not isinstance(module_target, str) or ":" not in module_target:
        warnings.append(
            f"script entry '{script_name}' has no 'module:func' shape: {module_target!r}"
        )
        return None, warnings

    package_module = module_target.split(":", 1)[0]
    # Convention: the `_commands/` directory lives at <package_module_path>/_commands/.
    # Map `agentfront.cli` → `<target>/agentfront/cli/`. We don't try to respect src-layouts
    # beyond the common case; src-layout users get a warning and a note.
    package_path_parts = package_module.split(".")
    candidate = target.joinpath(*package_path_parts)
    if not candidate.is_dir():
        src_candidate = target / "src" / Path(*package_path_parts)
        if src_candidate.is_dir():
            candidate = src_candidate
        else:
            warnings.append(
                f"cannot locate package directory for '{package_module}' under {target}; "
                "checked both flat and src/ layouts."
            )

    info = _TargetInfo(
        path=target,
        project_name=project_name if isinstance(project_name, str) else None,
        script_name=script_name,
        module_target=module_target,
        package_module=package_module,
        package_root=candidate,
    )
    if len(scripts) > 1:
        others = ", ".join(k for k in scripts.keys() if k != script_name)
        warnings.append(
            f"pyproject declares multiple scripts; overview inspects '{script_name}' only "
            f"(others: {others})."
        )
    return info, warnings


def _emit_project_root_section(report: OverviewReport, info: _TargetInfo) -> None:
    body_lines = [
        f"- **Project root:** `{info.path}`",
        f"- **Project name:** `{info.project_name}`" if info.project_name else "",
        f"- **Script:** `{info.script_name}` → `{info.module_target}`",
        f"- **Package:** `{info.package_module}`",
    ]
    body_lines = [line for line in body_lines if line]
    report.sections.append(
        OverviewSection(
            heading="Project root",
            body_md="\n".join(body_lines),
            findings=[
                {"key": "path", "value": str(info.path)},
                {"key": "project_name", "value": info.project_name},
                {"key": "script_name", "value": info.script_name},
                {"key": "module_target", "value": info.module_target},
                {"key": "package_module", "value": info.package_module},
            ],
        )
    )


def _emit_command_surface_section(report: OverviewReport, info: _TargetInfo) -> None:
    commands_dir = info.package_root / "_commands"
    findings: list[dict[str, object]] = []
    if not commands_dir.is_dir():
        body = (
            f"No `_commands/` directory at `{commands_dir}`. The target CLI does not "
            "follow the noun/verb `_commands/` layout; static command enumeration "
            "is not possible."
        )
        report.warnings.append(
            f"no _commands/ directory at {commands_dir}; command surface unknown."
        )
        report.sections.append(
            OverviewSection(heading="Command surface", body_md=body, findings=findings)
        )
        return

    items: list[str] = []
    for entry in sorted(commands_dir.iterdir()):
        if entry.name.startswith("_") or entry.suffix != ".py":
            continue
        name = entry.stem
        verbs = _scan_verbs(entry)
        if verbs:
            verb_list = ", ".join(f"`{v}`" for v in verbs)
            items.append(f"- **`{name}`** (noun) → verbs: {verb_list}")
            findings.append({"command": name, "kind": "noun", "verbs": verbs})
        else:
            items.append(f"- **`{name}`** (global verb)")
            findings.append({"command": name, "kind": "verb", "verbs": []})

    if not items:
        body = f"`_commands/` exists at `{commands_dir}` but is empty."
        report.warnings.append(f"empty _commands/ directory at {commands_dir}.")
    else:
        body = f"Detected from `{commands_dir}`:\n\n" + "\n".join(items)
    report.sections.append(
        OverviewSection(heading="Command surface", body_md=body, findings=findings)
    )


def _scan_verbs(source: Path) -> list[str]:
    """Best-effort regex scan for ``sub.add_parser("<verb>")`` calls."""
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return []
    matches = _ADD_PARSER_RE.findall(text)
    # The first add_parser in a noun module is typically the noun itself;
    # de-dup and also drop it if it matches the filename (self-registration).
    seen: list[str] = []
    for m in matches:
        if m == source.stem:
            continue
        if m not in seen:
            seen.append(m)
    return seen


def _emit_agent_first_triple_section(report: OverviewReport, info: _TargetInfo) -> None:
    commands_dir = info.package_root / "_commands"
    present: dict[str, bool] = dict.fromkeys(_UNIVERSAL_VERBS, False)
    if commands_dir.is_dir():
        for verb in _UNIVERSAL_VERBS:
            present[verb] = (commands_dir / f"{verb}.py").is_file()

    body_lines = ["Universal verbs an agent expects on any agent-first CLI:", ""]
    for verb in _UNIVERSAL_VERBS:
        mark = "✅" if present[verb] else "❌"
        body_lines.append(f"- {mark} `{info.script_name} {verb}`")
    missing = [v for v, ok in present.items() if not ok]
    if missing:
        body_lines.append("")
        body_lines.append(
            f"Missing verbs: {', '.join(missing)}. "
            "Wire them on the host App (see `agentfront learn`) so every "
            "surface exposes the agent-first universals."
        )
    report.sections.append(
        OverviewSection(
            heading="Agent-first universals",
            body_md="\n".join(body_lines),
            findings=[{"verb": v, "present": present[v]} for v in _UNIVERSAL_VERBS],
        )
    )


def _emit_rubric_posture_section(report: OverviewReport, info: _TargetInfo) -> None:
    has_tests = (info.path / "tests").is_dir()
    body_lines = [
        f"- Rubric grade: run `agentfront cli doctor {info.path}` (not invoked by overview).",
        f"- Tests dir: {'present' if has_tests else 'missing'} (`tests/`)",
    ]
    report.sections.append(
        OverviewSection(
            heading="Rubric posture",
            body_md="\n".join(body_lines),
            findings=[
                {"key": "tests_dir", "value": has_tests},
            ],
        )
    )


# ---------------------------------------------------------------------------
# Zero-target fallback
# ---------------------------------------------------------------------------


def _zero_target_report(
    *, warning: str | None = None, attempted_path: str | None = None
) -> OverviewReport:
    """Describe agentfront's own runtime model.

    Used when no ``path`` was given, or the target has no detectable CLI
    surface. agentfront is an importable runtime: a host package builds an
    :class:`agentfront.App`, declares docs and tools once, and derives the
    CLI / MCP / HTTP surfaces from that single registry. This report
    describes that model — it reads no files, so it is deterministic and
    complete.
    """
    report = OverviewReport(subject="cli", path=attempted_path)
    if warning:
        report.warnings.append(warning)

    report.sections.append(_build_runtime_intro_section())
    report.sections.append(_build_runtime_triple_section())

    report.notes.append(
        "wire your tool: `from agentfront import App` → declare docs/tools once → "
        "derive surfaces with `app.cli()` / `app.mcp_server()` / `app.http_app()`."
    )
    report.notes.append(
        "audit a target CLI: `agentfront cli doctor <path>` "
        "(see `agentfront explain cli doctor`)."
    )
    return report


def _build_runtime_intro_section() -> OverviewSection:
    return OverviewSection(
        heading="agentfront runtime model",
        body_md=(
            "No target CLI to inspect; describing agentfront's own runtime model.\n\n"
            "agentfront is an importable library, not a scaffolder. A host package "
            "builds one `App`, declares its docs and tools once, and derives all "
            "three agent-first surfaces from that single registry:\n\n"
            "```python\n"
            "from agentfront import App\n\n"
            'app = App(name="mytool", version="1.0")\n'
            'app.add_docs_dir("docs/")\n\n'
            "@app.tool\n"
            "def search(query: str) -> str:\n"
            '    """Search the corpus."""\n'
            "    ...\n\n"
            "app.cli()          # argparse CLI (learn / doctor)\n"
            "app.mcp_server()   # MCP server (minimal tool menu)\n"
            "app.http_app()     # WSGI site (markdown pages + sitemap)\n"
            "```"
        ),
        findings=[
            {"key": "model", "value": "importable-runtime"},
            {"key": "entrypoint", "value": "agentfront.App"},
            {"key": "surfaces", "value": ["cli", "mcp", "http"]},
        ],
    )


def _build_runtime_triple_section() -> OverviewSection:
    body_lines = ["Universal verbs every agent-first CLI surface ships:", ""]
    for verb in _UNIVERSAL_VERBS:
        body_lines.append(f"- `{verb}`")
    return OverviewSection(
        heading="Agent-first universals",
        body_md="\n".join(body_lines),
        findings=[{"verb": v, "present": True} for v in _UNIVERSAL_VERBS],
    )
