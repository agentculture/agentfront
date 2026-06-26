"""Subprocess-backed :class:`Runner` implementation.

Resolution strategy (in order):

1. ``uv run --project <cwd> <tool> --help`` — project-scoped. If the target
   is a uv-managed Python project, this is guaranteed to audit **that
   project's** entry point, not a same-named binary that happens to be on
   PATH. Takes the cache-warm path if uv has already synced.
2. ``<tool> --help`` — direct invocation. Fallback for non-uv projects or
   when ``uv`` is unavailable.

We probe ``--help`` (not ``--version``) because the rubric requires
``<tool> --help`` to exit 0 for bundle 1; ``--version`` is not in scope and
a conformant tool may not implement it.
"""

from __future__ import annotations

import subprocess  # noqa: S404 — the whole point of this module
from dataclasses import dataclass, field
from pathlib import Path

from agentfront.cli._errors import EXIT_ENV_ERROR, AgentfrontError
from agentfront.rubric._types import RunOutput

_UV_RUN_TIMEOUT = 30.0
_DIRECT_PROBE_TIMEOUT = 5.0


@dataclass
class SubprocessRunner:
    cwd: Path
    tool_name: str
    _base_argv: list[str] = field(default_factory=list, init=False, repr=False)

    def _resolve_base(self) -> list[str]:
        if self._base_argv:
            return self._base_argv

        # Project-scoped first: uv run --project <cwd> <tool> --help.
        uv_argv = [
            "uv",
            "run",
            "--project",
            str(self.cwd),
            self.tool_name,
        ]
        try:
            proc = subprocess.run(  # noqa: S603, S607 - uv is on PATH by convention
                [*uv_argv, "--help"],
                capture_output=True,
                text=True,
                timeout=_UV_RUN_TIMEOUT,
                check=False,
            )
            if proc.returncode == 0:
                self._base_argv = uv_argv
                return self._base_argv
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Direct invocation fallback.
        try:
            proc = subprocess.run(  # noqa: S603 - argv is controlled
                [self.tool_name, "--help"],
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=_DIRECT_PROBE_TIMEOUT,
                check=False,
            )
            if proc.returncode == 0:
                self._base_argv = [self.tool_name]
                return self._base_argv
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        raise AgentfrontError(
            code=EXIT_ENV_ERROR,
            message=f"cannot invoke '{self.tool_name}' in {self.cwd}",
            remediation=(
                f"run 'uv sync' in '{self.cwd}' so the tool is installed, "
                "or ensure the tool is on PATH"
            ),
        )

    def run(self, args: list[str], *, timeout: float = 10.0) -> RunOutput:
        argv = self._resolve_base() + list(args)
        cwd = self.cwd if argv[0] != "uv" else None
        proc = subprocess.run(  # noqa: S603 - argv is controlled
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return RunOutput(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
