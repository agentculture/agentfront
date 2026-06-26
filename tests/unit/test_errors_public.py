"""t1 acceptance: the structured error type is public, argparse-free, and the
legacy ``AfiError`` identifier is gone (rename completed, not aliased).

Covers plan targets c38 / the deferred PR #22 rename.
"""

from __future__ import annotations

import pathlib

import agentfront
from agentfront.errors import AgentfrontError

_PKG_ROOT = pathlib.Path(agentfront.__file__).parent
_LEGACY = "Afi" + "Error"  # avoid embedding the literal so the guard can't self-match


def test_public_import_and_top_level_reexport() -> None:
    # Importable from the public module and re-exported at the package root.
    assert agentfront.AgentfrontError is AgentfrontError


def test_errors_module_does_not_import_argparse() -> None:
    src = (_PKG_ROOT / "errors.py").read_text(encoding="utf-8")
    assert "import argparse" not in src
    assert "argparse" not in src


def test_to_dict_shape() -> None:
    err = AgentfrontError(code=1, message="x", remediation="y")
    assert err.to_dict() == {"code": 1, "message": "x", "remediation": "y"}
    # remediation defaults to empty string
    assert AgentfrontError(code=2, message="m").to_dict()["remediation"] == ""


def test_cli_errors_reexports_same_type() -> None:
    from agentfront.cli import _errors

    assert _errors.AgentfrontError is AgentfrontError


def test_no_legacy_identifier_remains_in_package() -> None:
    offenders = [
        str(p.relative_to(_PKG_ROOT))
        for p in _PKG_ROOT.rglob("*.py")
        if _LEGACY in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"retired identifier still present in: {offenders}"
