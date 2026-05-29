"""Guard test: ``agentfront cli cite`` must not touch anything outside ``.agentfront/``
and the single ``.gitignore`` line.
"""

from __future__ import annotations

import hashlib
import subprocess  # noqa: S404
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run_agentfront(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "agentfront", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _snapshot(root: Path, skip: tuple[str, ...]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if parts and parts[0] in skip:
            continue
        snapshot[str(rel)] = _hash(p)
    return snapshot


def test_cite_does_not_touch_unrelated_files(tmp_path: Path) -> None:
    # Populate the target with a handful of unrelated files.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# demo\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion="0"\n')

    before = _snapshot(tmp_path, skip=(".agentfront", ".gitignore"))

    result = _run_agentfront("cli", "cite", str(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    after = _snapshot(tmp_path, skip=(".agentfront", ".gitignore"))
    assert before == after, (
        f"cite modified files outside .agentfront/ and .gitignore: "
        f"{set(before.keys()) ^ set(after.keys())} / "
        f"changed: {[k for k in before if after.get(k) != before[k]]}"
    )


def test_cite_appends_gitignore_without_overwriting(tmp_path: Path) -> None:
    existing = "# user-maintained\n*.pyc\nlogs/\n"
    (tmp_path / ".gitignore").write_text(existing)

    _run_agentfront("cli", "cite", str(tmp_path), cwd=tmp_path)

    after = (tmp_path / ".gitignore").read_text()
    assert existing in after
    assert ".agentfront/" in after


def test_cite_preserves_gitignore_when_afi_already_ignored(tmp_path: Path) -> None:
    existing = "*.pyc\n.agentfront/\n"
    (tmp_path / ".gitignore").write_text(existing)

    _run_agentfront("cli", "cite", str(tmp_path), cwd=tmp_path)

    assert (tmp_path / ".gitignore").read_text() == existing
