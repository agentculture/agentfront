"""Overview — descriptive, read-only surface snapshots.

``overview`` reports what is *present* in a subject (a CLI, an MCP server, an
HTTP site). It never grades, never modifies, never spawns subprocesses in the
target. Complex diagnostic logic is deliberately pushed into agent-authored
skills; this module produces a tight structural report with ``> ⚠️`` and
``> note:`` inlines where it cannot deterministically answer.

Public surface:

- :class:`OverviewReport` — the report shape (subject, path, sections,
  warnings, notes).
- :class:`OverviewSection` — one markdown-rendered section with structured
  findings for JSON consumers.
- :func:`build` — factory that dispatches to a subject-specific inspector.
- :func:`to_markdown`, :func:`to_json_dict` — renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from afi.cli._errors import EXIT_USER_ERROR, AfiError

__all__ = [
    "OverviewReport",
    "OverviewSection",
    "SUBJECTS",
    "build",
    "to_json_dict",
    "to_markdown",
]


@dataclass
class OverviewSection:
    """One markdown-rendered section of an overview report."""

    heading: str
    body_md: str
    findings: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "heading": self.heading,
            "body_md": self.body_md,
            "findings": list(self.findings),
        }


@dataclass
class OverviewReport:
    """Read-only descriptive snapshot of a subject."""

    subject: str
    path: str | None
    sections: list[OverviewSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return to_json_dict(self)


SUBJECTS: tuple[str, ...] = ("cli", "all")


def build(subject: str, path: Path | None) -> OverviewReport:
    """Build a report for ``subject`` at ``path`` (``None`` → zero-target).

    ``subject`` must be in :data:`SUBJECTS`. Unknown subjects raise
    :class:`AfiError` with a remediation pointing at the accepted set.
    """
    if subject == "cli":
        # Local import to avoid cycles at module init.
        from afi.overview.cli_surface import inspect

        return inspect(path)
    if subject == "all":
        from afi.overview.cli_surface import inspect

        cli_report = inspect(path)
        cli_report.subject = "all"
        cli_report.notes.append(
            "mcp and site surfaces are not yet implemented (planned for v0.4 / v0.5); "
            "`afi overview` currently reports only the cli surface."
        )
        return cli_report
    raise AfiError(
        code=EXIT_USER_ERROR,
        message=f"unknown overview subject: {subject}",
        remediation=f"valid subjects: {', '.join(SUBJECTS)}",
    )


def to_markdown(report: OverviewReport) -> str:
    """Render ``report`` as markdown. Deterministic, no trailing blank line."""
    lines: list[str] = []
    target = report.path if report.path is not None else "<afi default template>"
    lines.append(f"# overview: {report.subject} — {target}")
    lines.append("")
    for section in report.sections:
        lines.append(f"## {section.heading}")
        lines.append("")
        body = section.body_md.rstrip()
        if body:
            lines.append(body)
            lines.append("")
    if report.warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in report.warnings:
            lines.append(f"> ⚠️ {w}")
        lines.append("")
    if report.notes:
        lines.append("## Notes for agents")
        lines.append("")
        for n in report.notes:
            lines.append(f"> note: {n}")
        lines.append("")
    # Trim the trailing blank line left by the last section.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def to_json_dict(report: OverviewReport) -> dict[str, object]:
    """Render ``report`` as a JSON-serialisable dict with stable keys."""
    return {
        "subject": report.subject,
        "path": report.path,
        "sections": [s.to_dict() for s in report.sections],
        "warnings": list(report.warnings),
        "notes": list(report.notes),
    }
