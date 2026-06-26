"""Unit tests for the doctor target-resolution helpers.

The integration suite covers the agent-visible CLI behaviour. These tests
pin the branch matrix on :func:`_resolve_package_source_root` directly,
since spinning up real editable installs in tempdirs to exercise every
PEP 610 edge case would slow the suite down for little gain.
"""

from __future__ import annotations

import json
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from agentfront.cli._commands.doctor import _resolve_package_source_root
from agentfront.cli._errors import AgentfrontError


class _FakeDist:
    """Minimal stand-in for :class:`importlib.metadata.Distribution`.

    Only :meth:`read_text` is exercised by the helper. We don't try to be
    a complete ``Distribution`` — over-faking would obscure which branch
    is actually under test.
    """

    def __init__(self, direct_url_payload: str | None) -> None:
        self._payload = direct_url_payload

    def read_text(self, name: str) -> str | None:
        if name == "direct_url.json":
            return self._payload
        return None


def _patch_distribution(monkeypatch: pytest.MonkeyPatch, payload: Any) -> None:
    """Install a fake ``importlib.metadata.distribution`` for the helper.

    ``payload`` is either a str (returned as direct_url.json) or an
    Exception class to raise (e.g. ``PackageNotFoundError``).
    """
    if isinstance(payload, type) and issubclass(payload, Exception):

        def _raise(_name: str) -> _FakeDist:
            raise payload()

        monkeypatch.setattr(
            "agentfront.cli._commands.doctor._metadata.distribution",
            _raise,
        )
        return
    fake = _FakeDist(payload)
    monkeypatch.setattr(
        "agentfront.cli._commands.doctor._metadata.distribution",
        lambda _name: fake,
    )


def test_missing_dist_raises_with_install_remediation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_distribution(monkeypatch, _metadata.PackageNotFoundError)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("ghost-package")
    assert "no installed distribution named 'ghost-package'" in exc_info.value.message
    assert "uv pip install -e" in exc_info.value.remediation


def test_missing_direct_url_signals_non_editable_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_distribution(monkeypatch, None)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("wheel-only")
    assert "not as an editable file:// install" in exc_info.value.message


def test_invalid_direct_url_json_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_distribution(monkeypatch, "{ not valid json")
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("corrupt-meta")
    assert "direct_url.json is not valid JSON" in exc_info.value.message


def test_non_file_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"url": "https://github.com/owner/repo.git"})
    _patch_distribution(monkeypatch, payload)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("vcs-only")
    assert "non-file source" in exc_info.value.message


def test_file_url_without_pyproject_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # tmp_path exists but has no pyproject.toml — same shape as a stale
    # editable record pointing at a deleted/moved repo.
    payload = json.dumps({"url": f"file://{quote(str(tmp_path))}", "dir_info": {"editable": True}})
    _patch_distribution(monkeypatch, payload)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("stale")
    assert "no pyproject.toml is there" in exc_info.value.message


def test_non_editable_file_install_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file:// install with ``dir_info.editable == False`` is not a valid target.

    The CLI help text scopes ``--package`` to *editable* installs; a plain
    ``pip install /path`` (no ``-e``) yields a file:// direct_url without
    the editable flag. Accepting that path silently would let ``--fix``
    mutate a tree the install copy isn't tracking.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    payload = json.dumps({"url": f"file://{quote(str(tmp_path))}", "dir_info": {"editable": False}})
    _patch_distribution(monkeypatch, payload)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("not-editable")
    assert "not editable" in exc_info.value.message
    assert "uv pip install -e" in exc_info.value.remediation


def test_file_install_without_dir_info_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``direct_url.json`` with no ``dir_info`` block is treated as non-editable.

    PEP 610 lets an installer omit ``dir_info``; absent the flag we can't
    prove editability, so the resolver must refuse rather than guess.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    payload = json.dumps({"url": f"file://{quote(str(tmp_path))}"})
    _patch_distribution(monkeypatch, payload)
    with pytest.raises(AgentfrontError) as exc_info:
        _resolve_package_source_root("no-dir-info")
    assert "not editable" in exc_info.value.message


def test_file_url_with_pyproject_returns_source_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    payload = json.dumps({"url": f"file://{quote(str(tmp_path))}", "dir_info": {"editable": True}})
    _patch_distribution(monkeypatch, payload)
    resolved = _resolve_package_source_root("demo")
    assert resolved == tmp_path.resolve()
