"""Tests for rubric core types."""

from __future__ import annotations

from pathlib import Path

from afi.rubric._types import CheckResult, RunOutput, VerifyContext


class _NoopRunner:
    def run(self, args: list[str], *, timeout: float = 10.0) -> RunOutput:
        return RunOutput(0, "", "")


def test_check_result_to_dict_shape() -> None:
    r = CheckResult("b", "c", True, "info", "e", "r")
    assert r.to_dict() == {
        "bundle": "b",
        "check": "c",
        "passed": True,
        "severity": "info",
        "evidence": "e",
        "remediation": "r",
        "auto_fixable": False,
        "fix_id": "",
    }


def test_check_result_carries_auto_fix_metadata() -> None:
    r = CheckResult(
        "b",
        "c",
        False,
        "error",
        "e",
        "r",
        auto_fixable=True,
        fix_id="my_fix",
    )
    payload = r.to_dict()
    assert payload["auto_fixable"] is True
    assert payload["fix_id"] == "my_fix"


def test_verify_context_defaults(tmp_path: Path) -> None:
    ctx = VerifyContext(target_path=tmp_path, tool_name="demo", runner=_NoopRunner())
    assert ctx.target_path == tmp_path
    assert ctx.tool_name == "demo"
    assert ctx.repo_files == []


def test_run_output_fields() -> None:
    out = RunOutput(1, "hello", "err")
    assert out.returncode == 1
    assert out.stdout == "hello"
    assert out.stderr == "err"
