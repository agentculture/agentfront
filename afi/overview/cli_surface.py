"""CLI-subject inspector — descriptive snapshot of a target CLI project.

Inspection strategy — **static only**. No subprocesses are spawned in the
target (that's what ``afi cli doctor`` is for; ``overview`` is the cheap
read-only survey that runs in milliseconds and never imports foreign code).

Two modes:

* **Target mode** — ``path`` points at a project with ``pyproject.toml`` +
  ``[project.scripts]``. We derive the module from the first script entry,
  walk ``<path>/<module>/cli/_commands/`` to enumerate the command surface,
  and scan each noun module's source for ``sub.add_parser("...")`` calls
  (best-effort — static regex, not a real AST).

* **Zero-target mode** — ``path`` is ``None`` or the target has no
  pyproject (fresh project, caller just wants to know what afi would
  scaffold). We describe afi's bundled reference template from
  ``afi/cite/references/python-cli/MANIFEST.json`` — afi knows its own
  creations perfectly, so this path is deterministic and complete.

The module never raises on inspection failure; it emits ``> ⚠️`` warnings
into the report and returns the best partial view it has. Callers get a
useful answer even on malformed targets.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from afi.overview import OverviewReport, OverviewSection

# Module-internal regex cache. Best-effort; a target CLI whose parser wiring
# uses a format the regex can't see is reported with a warning, not a crash.
_ADD_PARSER_RE = re.compile(r'add_parser\(\s*[\'"]([^\'"]+)[\'"]')

# Agent-first universal verbs. v0.5 expanded the set from the introspection
# triple (learn/explain/overview) to include the diagnosability pillar
# (doctor); the constant name avoids fixed arity ("triple") so it can grow
# further if afi mandates another verb in a future version.
_UNIVERSAL_VERBS = ("learn", "explain", "overview", "doctor")

# Where afi's bundled reference template lives (for the zero-target fallback).
_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "cite" / "references" / "python-cli"


@dataclass
class _TargetInfo:
    """Resolved static metadata about a target project."""

    path: Path
    project_name: str | None
    script_name: str
    module_target: str  # e.g. "afi.cli:main"
    package_module: str  # e.g. "afi.cli" (the :main half stripped)
    package_root: Path  # e.g. <path>/afi/cli/


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
            warning=f"path does not exist: {target}; falling back to afi's default template.",
            attempted_path=str(target),
        )

    pyproject = target / "pyproject.toml"
    if not pyproject.is_file():
        return _zero_target_report(
            warning=(
                f"no pyproject.toml at {pyproject}; target has no detectable CLI surface, "
                "falling back to afi's default template."
            ),
            attempted_path=str(target),
        )

    info, parse_warnings = _resolve_target_info(target, pyproject)
    if info is None:
        # _resolve_target_info returned warnings but could not identify a script.
        report = _zero_target_report(
            warning=(
                f"{pyproject} has no usable [project.scripts] entry; "
                "falling back to afi's default template."
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
    report.notes.append(f"for rubric grading (pass/fail), run: afi cli doctor {target}")
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
    # entry points can run `afi cli overview` once per entry in future
    # iterations; v0.3 inspects the first and notes the others.
    script_name, module_target = next(iter(scripts.items()))
    if not isinstance(module_target, str) or ":" not in module_target:
        warnings.append(
            f"script entry '{script_name}' has no 'module:func' shape: {module_target!r}"
        )
        return None, warnings

    package_module = module_target.split(":", 1)[0]
    # Convention: the `_commands/` directory lives at <package_module_path>/_commands/.
    # Map `afi.cli` → `<target>/afi/cli/`. We don't try to respect src-layouts
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
            "follow afi's scaffolded layout; static command enumeration is not possible."
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
            f"Run `afi cli cite {info.path}` to scaffold the reference pattern."
        )
    report.sections.append(
        OverviewSection(
            heading="Agent-first universals",
            body_md="\n".join(body_lines),
            findings=[{"verb": v, "present": present[v]} for v in _UNIVERSAL_VERBS],
        )
    )


def _emit_rubric_posture_section(report: OverviewReport, info: _TargetInfo) -> None:
    cited_dir = info.path / ".afi" / "reference" / "python-cli"
    cited = cited_dir.is_dir()
    has_tests = (info.path / "tests").is_dir()
    body_lines = [
        f"- Rubric grade: run `afi cli doctor {info.path}` (not invoked by overview).",
        f"- Tests dir: {'present' if has_tests else 'missing'} (`tests/`)",
        f"- afi reference tree cited: {'yes' if cited else 'no'}"
        + (f" (at `{cited_dir}`)" if cited else ""),
    ]
    report.sections.append(
        OverviewSection(
            heading="Rubric posture",
            body_md="\n".join(body_lines),
            findings=[
                {"key": "tests_dir", "value": has_tests},
                {"key": "reference_cited", "value": cited},
                {"key": "reference_path", "value": str(cited_dir) if cited else None},
            ],
        )
    )


# ---------------------------------------------------------------------------
# Zero-target fallback
# ---------------------------------------------------------------------------


def _zero_target_report(
    *, warning: str | None = None, attempted_path: str | None = None
) -> OverviewReport:
    """Describe afi's bundled CLI reference template.

    Used when no ``path`` was given, or the target has no detectable CLI
    surface. Reads ``afi/cite/references/python-cli/MANIFEST.json`` — afi
    knows its own scaffolded template exactly, so this report is complete
    and deterministic.
    """
    report = OverviewReport(subject="cli", path=attempted_path)
    if warning:
        report.warnings.append(warning)

    manifest = _load_template_manifest(report)
    if manifest is None:
        return report

    files = manifest.get("files", []) if isinstance(manifest, dict) else []
    tokens = manifest.get("tokens", {}) if isinstance(manifest, dict) else {}

    report.sections.append(_build_template_intro_section(manifest, files))
    tokens_section = _build_tokens_section(tokens)
    if tokens_section is not None:
        report.sections.append(tokens_section)
    inventory_section = _build_inventory_section(files)
    if inventory_section is not None:
        report.sections.append(inventory_section)
    report.sections.append(_build_template_triple_section(files))

    report.notes.append(
        "scaffold into a real project: `afi cli cite <path>` (see `afi explain cli cite`)."
    )
    report.notes.append("then audit: `afi cli doctor <path>` (see `afi explain cli doctor`).")
    return report


def _load_template_manifest(report: OverviewReport) -> dict | None:
    """Load MANIFEST.json; append a warning to ``report`` and return None on failure."""
    manifest_path = _TEMPLATE_ROOT / "MANIFEST.json"
    if not manifest_path.is_file():
        report.warnings.append(
            f"afi's bundled template is missing at {manifest_path}; "
            "this is a packaging bug, please file an issue."
        )
        return None
    try:
        return json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as err:
        report.warnings.append(f"could not read afi's bundled manifest: {err}")
        return None


def _build_template_intro_section(manifest: dict, files: list) -> OverviewSection:
    return OverviewSection(
        heading="afi default template",
        body_md=(
            "No target CLI to inspect; showing the reference tree afi would "
            "scaffold when you run `afi cli cite <path>`.\n\n"
            f"- **Language:** `{manifest.get('lang', 'unknown')}`\n"
            f"- **Source:** `{_TEMPLATE_ROOT}`\n"
            f"- **File count:** {len(files)}"
        ),
        findings=[
            {"key": "lang", "value": manifest.get("lang")},
            {"key": "template_root", "value": str(_TEMPLATE_ROOT)},
            {"key": "file_count", "value": len(files)},
        ],
    )


def _build_tokens_section(tokens: dict) -> OverviewSection | None:
    if not tokens:
        return None
    lines = ["Agents consuming the scaffolded tree substitute these tokens:", ""]
    for tok, desc in tokens.items():
        lines.append(f"- `{{{{{tok}}}}}` — {desc}")
    return OverviewSection(
        heading="Tokens",
        body_md="\n".join(lines),
        findings=[{"token": t, "description": d} for t, d in tokens.items()],
    )


def _build_inventory_section(files: list) -> OverviewSection | None:
    by_role: dict[str, list[dict]] = {}
    for f in files:
        if not isinstance(f, dict):
            continue
        role = f.get("role", "unknown")
        by_role.setdefault(role, []).append(f)

    body_lines: list[str] = []
    for role in sorted(by_role.keys()):
        body_lines.append(f"### {role}")
        body_lines.append("")
        for f in by_role[role]:
            body_lines.append(f"- `{f.get('path', '?')}` — {f.get('summary', '')}")
        body_lines.append("")
    if not body_lines:
        return None
    return OverviewSection(
        heading="File inventory",
        body_md="\n".join(body_lines).rstrip(),
        findings=[
            {"path": f.get("path"), "role": f.get("role"), "summary": f.get("summary")}
            for f in files
            if isinstance(f, dict)
        ],
    )


def _build_template_triple_section(files: list) -> OverviewSection:
    commands = [
        f.get("path", "")
        for f in files
        if isinstance(f, dict) and "/cli/_commands/" in f.get("path", "")
    ]
    universals_present = {v: any(c.endswith(f"{v}.py") for c in commands) for v in _UNIVERSAL_VERBS}
    body_lines = ["Universal verbs the scaffolded CLI ships with:", ""]
    for verb in _UNIVERSAL_VERBS:
        mark = "✅" if universals_present[verb] else "❌"
        body_lines.append(f"- {mark} `{verb}`")
    missing = [v for v, ok in universals_present.items() if not ok]
    if missing:
        body_lines.append("")
        body_lines.append(
            "The template does not yet scaffold: " + ", ".join(missing) + ". "
            "afi is tracked to add them as it grows."
        )
    return OverviewSection(
        heading="Agent-first universals (template)",
        body_md="\n".join(body_lines),
        findings=[{"verb": v, "present": universals_present[v]} for v in _UNIVERSAL_VERBS],
    )
