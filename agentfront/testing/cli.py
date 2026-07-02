"""In-process CLI harness — capture ``cli_surface.run_cli`` output for assertions.

Wraps :func:`agentfront.cli_surface.run_cli` with
``contextlib.redirect_stdout``/``redirect_stderr`` so consumer test suites can
call a host app's CLI in-process and assert on exit code + captured output
without shelling out to a subprocess.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass

from agentfront.app import App
from agentfront.cli_surface import run_cli as _cli_surface_run_cli

__all__ = ["CliResult", "run_cli"]


@dataclass(frozen=True)
class CliResult:
    """The captured, immutable result of one in-process CLI invocation."""

    exit_code: int
    stdout: str
    stderr: str


def run_cli(app: App, argv: list[str]) -> CliResult:
    """Run *app*'s CLI in-process against *argv*, capturing stdout/stderr.

    Delegates to :func:`agentfront.cli_surface.run_cli` (the same dispatch a
    real CLI invocation uses) but redirects its stdout/stderr writes into
    in-memory buffers instead of the real streams — no subprocess, so this is
    fast and safe to call from pytest.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        exit_code = _cli_surface_run_cli(app, argv)
    return CliResult(
        exit_code=exit_code,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )
