"""Tests for :mod:`agentfront.cite._engine`."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfront.cite import SUPPORTED_LANGS, CiteReport, emit_reference
from agentfront.cite._engine import GITIGNORE_ENTRY
from agentfront.cli._errors import AfiError


def test_emit_reference_writes_files(tmp_path: Path) -> None:
    report = emit_reference(tmp_path, lang="python")

    assert isinstance(report, CiteReport)
    assert report.out == tmp_path / ".agentfront" / "reference" / "python-cli"
    assert report.out.is_dir()
    assert report.written_count > 0

    # Key reference files are present.
    assert (report.out / "AGENT.md").is_file()
    assert (report.out / "MANIFEST.json").is_file()
    assert (report.out / "{{slug}}" / "cli" / "_errors.py").is_file()


def test_tokens_remain_literal(tmp_path: Path) -> None:
    report = emit_reference(tmp_path, lang="python")

    cli_init = (report.out / "{{slug}}" / "cli" / "__init__.py").read_text()
    assert "{{project_name}}" in cli_init
    assert "{{module}}" in cli_init
    # The cite engine MUST NOT substitute tokens.
    assert "agentfront" not in cli_init


def test_gitignore_created_when_missing(tmp_path: Path) -> None:
    gi = tmp_path / ".gitignore"
    assert not gi.exists()

    report = emit_reference(tmp_path, lang="python")

    assert report.gitignore_updated is True
    assert gi.read_text().strip().endswith(GITIGNORE_ENTRY)


def test_gitignore_appended_when_afi_line_missing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("# existing\n*.pyc\n")

    report = emit_reference(tmp_path, lang="python")

    assert report.gitignore_updated is True
    body = (tmp_path / ".gitignore").read_text()
    assert "*.pyc" in body  # pre-existing preserved
    assert GITIGNORE_ENTRY in body


def test_gitignore_unchanged_when_afi_already_ignored(tmp_path: Path) -> None:
    before = "# existing\n.agentfront/\nlogs/\n"
    (tmp_path / ".gitignore").write_text(before)

    report = emit_reference(tmp_path, lang="python")

    assert report.gitignore_updated is False
    assert (tmp_path / ".gitignore").read_text() == before


@pytest.mark.parametrize("existing", [".agentfront", ".agentfront/", ".agentfront/**"])
def test_gitignore_equivalents_detected(tmp_path: Path, existing: str) -> None:
    (tmp_path / ".gitignore").write_text(f"{existing}\n")

    report = emit_reference(tmp_path, lang="python")

    assert report.gitignore_updated is False


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    emit_reference(tmp_path, lang="python")
    # Simulate stale edits in the reference dir.
    marker = tmp_path / ".agentfront" / "reference" / "python-cli" / "STALE.txt"
    marker.write_text("stale")
    assert marker.exists()

    emit_reference(tmp_path, lang="python")

    # Wiped on re-run.
    assert not marker.exists()
    assert (tmp_path / ".agentfront" / "reference" / "python-cli" / "AGENT.md").is_file()


def test_out_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom" / "place"
    report = emit_reference(tmp_path, lang="python", out=custom)

    assert report.out == custom
    assert (custom / "AGENT.md").is_file()


def test_unsupported_lang_raises_user_error(tmp_path: Path) -> None:
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path, lang="cobol")
    assert exc.value.code == 1
    assert "supported langs" in exc.value.remediation


def test_missing_target_dir_raises_user_error(tmp_path: Path) -> None:
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path / "does-not-exist", lang="python")
    assert exc.value.code == 1


def test_target_that_is_a_file_raises_user_error(tmp_path: Path) -> None:
    # target exists but is a regular file — caught by the is_dir check after resolve.
    f = tmp_path / "a-file"
    f.write_text("x")
    with pytest.raises(AfiError) as exc:
        emit_reference(f, lang="python")
    assert exc.value.code == 1
    assert "not a directory" in exc.value.message


def test_out_outside_target_is_rejected(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """--out pointing outside the target must be rejected before rmtree/copytree."""
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path, lang="python", out=elsewhere / "ref")
    assert exc.value.code == 1
    assert "must be inside" in exc.value.message


def test_out_via_traversal_is_rejected(tmp_path: Path) -> None:
    """`--out <target>/../sibling` is caught because we resolve first."""
    sibling = tmp_path.parent / (tmp_path.name + "_sibling")
    sibling.mkdir(exist_ok=True)
    traversal = tmp_path / ".." / sibling.name
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path, lang="python", out=traversal)
    assert exc.value.code == 1
    assert "inside" in exc.value.message or "inside" in exc.value.remediation


def test_out_equals_target_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path, lang="python", out=tmp_path)
    assert exc.value.code == 1
    assert "target path" in exc.value.message


def test_out_that_is_an_existing_file_is_rejected(tmp_path: Path) -> None:
    conflict = tmp_path / "clobber"
    conflict.write_text("x")  # exists as a FILE inside target
    with pytest.raises(AfiError) as exc:
        emit_reference(tmp_path, lang="python", out=conflict)
    assert exc.value.code == 1
    assert "not a directory" in exc.value.message


def test_supported_langs_contains_python() -> None:
    assert "python" in SUPPORTED_LANGS


def test_report_to_dict_shape(tmp_path: Path) -> None:
    report = emit_reference(tmp_path, lang="python")
    d = report.to_dict()

    assert d["out"] == str(report.out)
    assert isinstance(d["written_count"], int) and d["written_count"] > 0
    assert d["gitignore_updated"] is True
    assert isinstance(d["next_steps"], list) and len(d["next_steps"]) == 3
    assert d["further_reading"]["agent_md"].endswith("AGENT.md")
    assert "agentfront explain cli cite" in d["further_reading"]["explain"]


def test_cited_manifest_is_valid_json(tmp_path: Path) -> None:
    import json

    report = emit_reference(tmp_path, lang="python")
    manifest = json.loads((report.out / "MANIFEST.json").read_text())

    assert manifest["lang"] == "python"
    assert "tokens" in manifest
    assert isinstance(manifest["files"], list) and len(manifest["files"]) > 5
    for entry in manifest["files"]:
        assert entry["role"] in {"stable-contract", "shape-adapt"}
