"""Cite engine — copies the reference tree and updates ``.gitignore``.

The operation is safe by construction:

* writes only under ``out`` (default ``<target>/.agentfront/reference/<lang>-cli/``);
* ``out`` is required to resolve to a path strictly inside ``target_path`` —
  this bounds the :func:`shutil.rmtree`/``copytree`` blast radius to the
  caller's project, mitigating path-injection (S2083) from a hostile
  ``--out`` override;
* adds one line to ``<target>/.gitignore`` only when ``.agentfront/`` is absent;
* touches nothing else in the target project;
* re-running wipes and re-copies ``out`` — always the latest reference.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from agentfront import _brand
from agentfront.cli._errors import EXIT_ENV_ERROR, EXIT_USER_ERROR, AfiError

SUPPORTED_LANGS = ("python",)

GITIGNORE_ENTRY = f"{_brand.DOTDIR}/"

_REFERENCES_DIR = Path(__file__).resolve().parent / "references"


@dataclass(frozen=True)
class CiteReport:
    out: Path
    written_count: int
    gitignore_updated: bool

    def describe_next_steps(self) -> list[str]:
        return [
            f"Read {self.out / 'AGENT.md'} — describes each file's role "
            "(stable-contract vs shape-adapt) and lists the {{tokens}} to substitute.",
            "Apply the pattern to your project: copy stable-contract files verbatim, "
            "reshape shape-adapt files to your module layout, then substitute "
            "{{project_name}}, {{slug}}, {{module}} throughout.",
            "Run `agentfront cli verify .` to confirm the result satisfies the agent-first rubric.",
        ]

    def to_dict(self) -> dict[str, object]:
        return {
            "out": str(self.out),
            "written_count": self.written_count,
            "gitignore_updated": self.gitignore_updated,
            "next_steps": self.describe_next_steps(),
            "further_reading": {
                "agent_md": str(self.out / "AGENT.md"),
                "explain": ["agentfront explain cli cite", "agentfront explain cli verify"],
            },
        }


def _validated_out(out: Path, target_path: Path) -> Path:
    """Resolve ``out`` and verify it sits strictly inside ``target_path``.

    This is the anti-path-injection gate. ``shutil.rmtree`` is destructive; we
    only accept an ``out`` that resolves to a descendant of the already
    resolved target directory. ``out == target_path`` is also rejected (would
    wipe the whole project). Symlinks are followed before comparison.
    """
    resolved = out.resolve()
    if resolved == target_path:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message="--out cannot equal the target path (would wipe the project)",
            remediation="pass a subpath inside the target, e.g. --out ./reference/",
        )
    try:
        resolved.relative_to(target_path)
    except ValueError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"--out must be inside the target path: {resolved} is not under {target_path}",
            remediation="pick a path inside the target project, or omit --out for the default",
        ) from err
    return resolved


def emit_reference(
    target_path: Path,
    *,
    lang: str = "python",
    out: Path | None = None,
) -> CiteReport:
    """Copy the ``lang`` reference tree into ``out`` and touch ``.gitignore``."""
    if lang not in SUPPORTED_LANGS:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"unsupported lang: {lang}",
            remediation=f"supported langs: {', '.join(SUPPORTED_LANGS)}",
        )
    try:
        target_path = target_path.resolve(strict=True)
    except FileNotFoundError as err:
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"target path does not exist: {target_path}",
            remediation="pass a path to an existing directory, or '.' for cwd",
        ) from err
    if not target_path.is_dir():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"target path is not a directory: {target_path}",
            remediation="pass a path to an existing directory, or '.' for cwd",
        )

    if out is None:
        out = target_path / _brand.DOTDIR / "reference" / f"{lang}-cli"
    # Canonicalise + validate: out must resolve inside target_path. Bounds the
    # blast radius of the `shutil.rmtree(out)` call below (CWE-22 / S2083).
    out = _validated_out(out, target_path)
    if out.exists() and not out.is_dir():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"--out exists but is not a directory: {out}",
            remediation="remove that file or pick a different --out",
        )

    src = _REFERENCES_DIR / f"{lang}-cli"
    if not src.is_dir():
        raise AfiError(
            code=EXIT_ENV_ERROR,
            message=f"reference tree missing at {src}",
            remediation="file a bug — reference data not packaged",
        )

    if out.exists():
        shutil.rmtree(out)  # out has been validated to live inside target_path
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, out)

    written = sum(1 for p in out.rglob("*") if p.is_file())
    gitignore_updated = _ensure_gitignore_line(target_path)

    return CiteReport(out=out, written_count=written, gitignore_updated=gitignore_updated)


def _ensure_gitignore_line(project_root: Path) -> bool:
    """Ensure ``GITIGNORE_ENTRY`` is present in ``<project_root>/.gitignore``.

    Security (S2083 defence in depth): ``project_root`` must be an already
    resolved, absolute directory. The callee *validates* that precondition
    before touching the filesystem, then constructs the path using a literal
    filename (``.gitignore``) — no user-controlled traversal component can
    escape ``project_root``.

    Returns ``True`` if the file was created or appended; ``False`` if the
    line (or an equivalent glob) was already present.
    """
    if not project_root.is_absolute() or not project_root.is_dir():
        raise AfiError(
            code=EXIT_USER_ERROR,
            message=f"project_root is not a resolved directory: {project_root}",
            remediation="pass an existing directory; '.' is resolved internally",
        )
    # Literal filename — the only path component we concatenate onto the
    # pre-validated project_root. S2083 sanitiser pattern: validated root +
    # static leaf = bounded write target.
    gitignore = project_root / ".gitignore"

    line = GITIGNORE_ENTRY
    equivalents = {line, line.rstrip("/"), line + "**", line.rstrip("/") + "/**"}
    if gitignore.is_file():
        existing = {s.strip() for s in gitignore.read_text().splitlines()}
        if existing & equivalents:
            return False
        body = gitignore.read_text()
        if body and not body.endswith("\n"):
            body += "\n"
        body += line + "\n"
        gitignore.write_text(body)
        return True
    gitignore.write_text(line + "\n")
    return True
