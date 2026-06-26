"""Tests for :mod:`agentfront.cli._errors`."""

from __future__ import annotations

import pytest

from agentfront.cli._errors import (
    EXIT_ENV_ERROR,
    EXIT_SUCCESS,
    EXIT_USER_ERROR,
    AgentfrontError,
)


def test_afi_error_carries_fields() -> None:
    err = AgentfrontError(code=1, message="bad input", remediation="try again")
    assert err.code == 1
    assert err.message == "bad input"
    assert err.remediation == "try again"


def test_afi_error_is_raisable() -> None:
    with pytest.raises(AgentfrontError) as exc:
        raise AgentfrontError(code=2, message="env broken", remediation="run uv sync")
    assert exc.value.code == 2
    assert "env broken" in str(exc.value)


def test_afi_error_default_remediation_empty() -> None:
    err = AgentfrontError(code=1, message="m")
    assert err.remediation == ""


def test_afi_error_to_dict_shape() -> None:
    err = AgentfrontError(code=1, message="m", remediation="r")
    assert err.to_dict() == {"code": 1, "message": "m", "remediation": "r"}


def test_exit_codes_documented() -> None:
    # Frozen policy — part of the public contract documented in `agentfront learn`.
    assert EXIT_SUCCESS == 0
    assert EXIT_USER_ERROR == 1
    assert EXIT_ENV_ERROR == 2
