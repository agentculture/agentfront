"""The teken compatibility wrapper must stay in lockstep with agentfront.

`packaging/teken/pyproject.toml` is a metadata-only distribution kept at full
parity with the canonical project: its own ``version``, its ``agentfront==`` pin,
and its ``agentfront[mcp]==`` extra-parity pin must all equal the root version,
so ``uv tool install teken`` / ``uv tool install "teken[mcp]"`` always resolve
the matching ``agentfront`` / ``agentfront[mcp]``.

This mirrors the CI "Check teken wrapper lockstep" guard in tests.yml as a fast
local regression — a bare ``version-bump`` run that forgets a pin fails here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_WRAPPER_PYPROJECT = _REPO_ROOT / "packaging" / "teken" / "pyproject.toml"


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text())


@pytest.fixture(scope="module")
def root_version() -> str:
    return _load(_ROOT_PYPROJECT)["project"]["version"]


@pytest.fixture(scope="module")
def wrapper() -> dict:
    return _load(_WRAPPER_PYPROJECT)["project"]


def test_wrapper_version_matches_root(root_version: str, wrapper: dict) -> None:
    assert wrapper["version"] == root_version


def test_wrapper_agentfront_pin_matches_root(root_version: str, wrapper: dict) -> None:
    assert wrapper["dependencies"] == [f"agentfront=={root_version}"]


def test_wrapper_mcp_extra_pin_matches_root(root_version: str, wrapper: dict) -> None:
    mcp_extra = wrapper["optional-dependencies"]["mcp"]
    assert mcp_extra == [f"agentfront[mcp]=={root_version}"]


def test_wrapper_stays_metadata_only() -> None:
    """No importable modules — only metadata + the agentfront dependency."""
    raw = _load(_WRAPPER_PYPROJECT)
    assert raw["tool"]["hatch"]["build"]["targets"]["wheel"]["bypass-selection"] is True
