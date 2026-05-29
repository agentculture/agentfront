"""Tests for rubric bundle 7: doctor."""

from __future__ import annotations

import json
from pathlib import Path

from agentfront.rubric._types import RunOutput, VerifyContext
from agentfront.rubric.checks import doctor as doctor_checks
from tests.unit._fake_runner import FakeRunner

_GOOD_PAYLOAD = {
    "tool": "demo",
    "subject": "demo self",
    "healthy": True,
    "checks": [
        {
            "id": "version_consistency",
            "bundle": "self",
            "passed": True,
            "severity": "info",
            "message": "ok",
            "remediation": "",
            "auto_fixable": False,
            "fix_id": "",
        },
    ],
    "summary": {"total": 1, "passed": 1, "failed": 0, "errors": 0, "warnings": 0},
}

_UNHEALTHY_WITH_REMEDIATION = {
    "tool": "demo",
    "subject": "demo self",
    "healthy": False,
    "checks": [
        {
            "id": "version_consistency",
            "bundle": "self",
            "passed": False,
            "severity": "error",
            "message": "drift",
            "remediation": "re-sync",
            "auto_fixable": True,
            "fix_id": "sync_version",
        }
    ],
    "summary": {"total": 1, "passed": 0, "failed": 1, "errors": 1, "warnings": 0},
}


def _ctx(tmp_path: Path, runner: FakeRunner) -> VerifyContext:
    return VerifyContext(tmp_path, "demo", runner)


def test_pass_on_healthy_doctor(tmp_path: Path) -> None:
    payload_str = json.dumps(_GOOD_PAYLOAD)
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(0, "doctor: healthy\n", ""),
            ("doctor", "--json"): RunOutput(0, payload_str, ""),
        }
    )
    results = doctor_checks.run(_ctx(tmp_path, runner))
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_fail_when_doctor_global_missing(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(2, "", "invalid choice: 'doctor'"),
            ("doctor", "--json"): RunOutput(2, "", ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    assert not by_name["doctor_global_exists"].passed
    assert by_name["doctor_global_exists"].severity == "error"
    assert "diagnosability" in by_name["doctor_global_exists"].remediation


def test_fail_when_json_not_parseable(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(0, "ok", ""),
            ("doctor", "--json"): RunOutput(0, "this is not json", ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    assert not by_name["doctor_json_shape"].passed


def test_fail_when_top_level_missing_keys(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(0, "ok", ""),
            ("doctor", "--json"): RunOutput(0, json.dumps({"foo": "bar"}), ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    result = by_name["doctor_json_shape"]
    assert not result.passed
    assert "healthy" in result.evidence or "checks" in result.evidence


def test_fail_when_healthy_is_not_bool(tmp_path: Path) -> None:
    payload = dict(_GOOD_PAYLOAD)
    payload["healthy"] = "yes"
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(0, "ok", ""),
            ("doctor", "--json"): RunOutput(0, json.dumps(payload), ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    assert not by_name["doctor_json_shape"].passed
    assert "bool" in by_name["doctor_json_shape"].evidence


def test_fail_when_check_entry_missing_keys(tmp_path: Path) -> None:
    payload = {
        "healthy": False,
        "checks": [{"id": "x", "passed": False}],  # missing severity, message
    }
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(0, "ok", ""),
            ("doctor", "--json"): RunOutput(0, json.dumps(payload), ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    assert not by_name["doctor_check_shape"].passed


def test_fail_when_unhealthy_without_remediation(tmp_path: Path) -> None:
    payload = {
        "healthy": False,
        "checks": [
            {
                "id": "x",
                "passed": False,
                "severity": "error",
                "message": "broken",
                # no remediation — bundle 7 promise broken.
            }
        ],
    }
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(1, "ok", ""),
            ("doctor", "--json"): RunOutput(1, json.dumps(payload), ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    assert not by_name["doctor_remediation_when_unhealthy"].passed
    assert "actionable" in by_name["doctor_remediation_when_unhealthy"].remediation


def test_pass_when_unhealthy_with_remediation(tmp_path: Path) -> None:
    runner = FakeRunner(
        responses={
            ("doctor",): RunOutput(1, "doctor: unhealthy\n", ""),
            ("doctor", "--json"): RunOutput(1, json.dumps(_UNHEALTHY_WITH_REMEDIATION), ""),
        }
    )
    by_name = {r.check: r for r in doctor_checks.run(_ctx(tmp_path, runner))}
    # healthy=False but every failed check has a remediation → pass.
    assert by_name["doctor_remediation_when_unhealthy"].passed
    # And the verb itself exists (non-empty stdout).
    assert by_name["doctor_global_exists"].passed
